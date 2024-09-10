import boto3
import json
import time
from botocore.config import Config  # Import Config for setting timeouts

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
        
        # Debugging: Print the input data retrieved from S3
        print(f"Retrieved input data from S3: {input_data.keys()}")
        
        # Process the input data (your custom logic goes here)
        result = process_input_data(input_data)
        
        # Debugging: Print the processed data before calling the generation Lambda
        print(f"Processed data to be sent to generation Lambda: {result['data']['userData'].keys()}")

        # Validate that the required fields are present
        if not result.get('data') or not ('userData' in result['data'] and 'rooms' in result['data']['userData']) and not ('areas' in result):
            raise ValueError("Invalid input: 'data.userData.rooms' or 'areas' not found.")
        
        # Invoke another Lambda with retry logic
        response = invoke_lambda_with_retry(result)

        # Read the response from the invoked Lambda function
        generation_response = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(generation_response['body'])
        
        # Extract only the first 'areas' list to reduce length
        areas = body.get('response', {}).get('floors', [{}])[0].get('designs', [{}])[0].get('areas', [])
        print(f"before SQS, the areas: {areas}")
        
        # Send the result to SQS
        sqs_message = {
            'job_id': job_id,
            'status': 'complete',
            'result': json.dumps({'areas': areas})  # Send actual result from the generation Lambda
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
            'body': json.dumps({'message': 'An error occurred during processing.', 'error': str(e)})
        }

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
            return response  # If successful, return the response
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with error: {str(e)}")
            if attempt < retries - 1:
                time.sleep(backoff_factor ** attempt)  # Backoff strategy
            else:
                raise  # Raise exception if all retries failed

def process_input_data(data):
    # Implement your custom processing logic here
    # Ensure that the data format matches the expected input for the generation Lambda

    # Check and ensure the correct structure
    if 'data' not in data:
        data['data'] = {}
    if 'userData' not in data['data']:
        data['data']['userData'] = {}
    if 'rooms' not in data['data']['userData']:
        data['data']['userData']['rooms'] = []  # or set it to some default value
    if 'areas' not in data:
        data['areas'] = []  # or set it to some default value

    # Return the modified data
    return data

def local_test():
    # Test input similar to the event from AWS Lambda
    test_event = {
        "job_id": "1725998880",
        "bucket": "bucketforbenchmarking",
        "key": "optimizer/floorplans/1725998880.json"
    }

    # Simulate the Lambda context (you can customize this object if needed)
    test_context = {}

    # Invoke the Lambda handler function locally
    print("Invoking lambda_handler locally with test input...")
    response = lambda_handler(test_event, test_context)
    
    # Print the response from the Lambda handler
    print("Lambda handler response:", json.dumps(response, indent=2))

if __name__ == "__main__":
    local_test()
