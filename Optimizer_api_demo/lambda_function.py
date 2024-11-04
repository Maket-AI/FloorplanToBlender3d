import boto3
import json
import time
from botocore.config import Config

# Set up the AWS SDK client with a longer read timeout and retry configuration
config = Config(
    region_name='ca-central-1',
    retries={'max_attempts': 3},  # Configure retry attempts
    read_timeout=900,  # Set the read timeout to 900 seconds (15 minutes)
    connect_timeout=60  # Set the connection timeout to 60 seconds
)

# Initialize the AWS clients with the configured timeout
sqs_client = boto3.client('sqs', config=config)
s3_client = boto3.client('s3', config=config)
lambda_client = boto3.client('lambda', config=config)

# Hardcode the SQS queue URL
SQS_QUEUE_URL = 'https://sqs.ca-central-1.amazonaws.com/898603082442/floorplan-renovation-queue'


def deserialize_nested_string(value):
    if not value:
        return value  # if the string is empty, just return it
    try:
        # Try to deserialize the value
        return json.loads(value)
    except json.JSONDecodeError:
        # If it's not a valid JSON, return the original value
        return value


def get_response_as_json(response):
    response_payload = json.loads(response["Payload"].read().decode("utf-8"))
    # print(type(response_payload))
    for k in response_payload:
        if isinstance(response_payload[k], str) and "first" in k:
            response_payload[k] = deserialize_nested_string(response_payload[k])
    return response_payload


def lambda_handler(event, context):
    try:
        # Extract job_id and S3 location from the event
        job_id = event.get('job_id')
        bucket = event.get('bucket')
        key = event.get('key')
        # Check if S3 bucket and key are provided
        if not bucket or not key:
            raise ValueError("S3 bucket and key are required.")
        # Retrieve data from S3
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        input_data = json.loads(s3_response['Body'].read().decode('utf-8'))
        print(f"Retrieved input data from S3: {input_data.keys()}")
        # Process the input data
        result = process_input_data(input_data)
        print(f"Processed data to be sent to generation Lambda: {result['data']['userData'].keys()}")

        # Validate required fields
        if not result.get('data') or not ('userData' in result['data'] and 'rooms' in result['data']['userData']) and not ('areas' in result):
            raise ValueError("Invalid input: 'data.userData.rooms' or 'areas' not found.")
        # Invoke another Lambda with retry logic
        response = invoke_lambda_with_retry(result)
        # Read the response from the invoked Lambda function
        generation_response = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(generation_response['body'])
        # Extract areas
        areas = body.get('response', {}).get('floors', [{}])[0].get('designs', [{}])[0].get('areas', [])
        print(f"before SQS for job_id {job_id}, the areas: {areas}")
        # Visualize and retrieve the remote image URL
        house = [{"rooms": body.get("response", {}).get("rooms", [{}])[0]}]
        remote_image = visualize_house_with_lambda(house)
        # Send the result to SQS
        sqs_message = {
            'job_id': job_id,
            'status': 'complete',
            'result': json.dumps({
                'areas': areas,
                'remote_image_url': remote_image if remote_image else "empty_url"
            })
        }
        sqs_response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(sqs_message)
        )

        print(f"SQS message sent. Message ID: {sqs_response['MessageId']}")

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Processing complete'})
        }

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'An error occurred during process.', 'error': str(e)})
        }


def visualize_house_with_lambda(house):
    if "rooms" in house[0]:
        plan_to_render = [house[0]["rooms"]]
    if len(house) == 2 and len(house[1]) == 2:
        plan_to_render = [house[1][0]["rooms"], house[1][1]["rooms"]]
    if len(house) == 2 and "rooms" in house[1]:
        plan_to_render = [house[0]["rooms"], house[1]["rooms"]]
        # print("Plan rooms:", plan["rooms"])
    lambda_client = boto3.client("lambda")
    visualizer_response = call_visualizer(plan_to_render, lambda_client)
    # print("VISUALIZER RESPONSE:", visualizer_response)
    print(visualizer_response["paths"])
    for j, house_image_paths in enumerate(visualizer_response["paths"]):
        for i, remote_image in enumerate(house_image_paths):
            print(f"House {i} image path:", remote_image)
    print("Visualized the house with lambda")
    return remote_image


def call_visualizer(
    plans_to_visualize: list,
    lambda_client,
    visualize_function_name="test-asyncPlanGenStack-VisualizePlanFunction-GbKUbaR4g7fl",
):
    messages = ""
    for plan in plans_to_visualize:
        for i, room in enumerate(plan):
            room["id"] = i
    invoke_payload = {
        "data": {
            "userID": "procthor_user",
            "plans": plans_to_visualize,
            "options": {
                "save_image": True,
                "first_floor_and_second_floor": len(plans_to_visualize) == 2,
            },
        }
    }

    # Lambda invocation
    try:
        response = lambda_client.invoke(
            FunctionName=visualize_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(invoke_payload),
        )
    except Exception as e:
        messages += (
            f"Error during Lambda invocation: {e}, with payload {invoke_payload}---"
        )
        print(messages)
        return {"Error messages": messages}, -99

    # Parsing response
    try:
        response = get_response_as_json(response)
        response = json.loads(response["body"])
    except Exception as e:
        messages += f"Error parsing response: {e}, with response: {response}---"
        print(messages)
        return {"Error messages": messages}, -99
    return response



def invoke_lambda_with_retry(payload, retries=3, backoff_factor=2):
    """
    Function to invoke a Lambda function with retry and exponential backoff.
    """
    for attempt in range(retries):
        try:
            response = lambda_client.invoke(
                FunctionName='dev-asyncPlanGenStack-OptimizerFunction-pvcuXetLNgvZ',
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            return response
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with error: {str(e)}")
            if attempt < retries - 1:
                time.sleep(backoff_factor ** attempt)
            else:
                raise

def process_input_data(data):
    # Ensure the correct structure for input data
    if 'data' not in data:
        data['data'] = {}
    if 'userData' not in data['data']:
        data['data']['userData'] = {}
    if 'rooms' not in data['data']['userData']:
        data['data']['userData']['rooms'] = []
    if 'areas' not in data:
        data['areas'] = []

    return data

def local_test():
    # Test input similar to the event from AWS Lambda
    test_event = {
        "job_id": "1725998880",
        "bucket": "bucketforbenchmarking",
        "key": "optimizer/floorplans/1725998880.json"
    }

    test_context = {}
    print("Invoking lambda_handler locally with test input...")
    response = lambda_handler(test_event, test_context)
    print("Lambda handler response:", json.dumps(response, indent=2))

if __name__ == "__main__":
    local_test()
