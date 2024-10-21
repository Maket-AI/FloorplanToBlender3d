from flask import Flask, request, jsonify, render_template, redirect, url_for
import json
import boto3
import os
import time
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# AWS Configuration
stored_floorplan_data = None  # Global variable to store the original floorplan data
config = Config(connect_timeout=5, read_timeout=900)
lambda_client = boto3.client('lambda', region_name=os.getenv('AWS_REGION'), config=config)
s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION'))
sqs_client = boto3.client('sqs', region_name=os.getenv('AWS_REGION'))

# Configuration
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')  # Set your S3 bucket name
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')  # Set your SQS queue URL

# Define ALL_ROOM_TYPES
ALL_ROOM_TYPES = [
    "living_room",
    "kitchen",
    "dining_room",
    "corridor",
    "entry",
    "bedroom",
    "bathroom",
    "garage",
    "laundry",
    "mudroom",
    "stair",
    "deck",
    "closet",
    "walk_in",
]

@app.route('/', methods=['GET'])
def home():
    """Home route to upload JSON file"""
    return render_template('home.html')

@app.route('/init_floorplan', methods=['POST'])
def init_floorplan():
    """Initialize floorplan after uploading JSON file"""
    global stored_floorplan_data
    file = request.files.get('floorplanner_plan')
    if file:
        try:
            data = file.read().decode('utf-8')
            stored_floorplan_data = json.loads(data)
            print('Loaded floorplan_data keys:', stored_floorplan_data.keys())

            unnamed_rooms = [idx for idx, area in enumerate(stored_floorplan_data['areas']) if not area.get('name')]

            if unnamed_rooms:
                return render_template(
                    'init_floorplan.html',
                    floorplan_data=stored_floorplan_data,
                    unnamed_rooms=unnamed_rooms,
                    all_room_types=ALL_ROOM_TYPES
                )

            return redirect(url_for('options'))
        except Exception as e:
            print(f"Error processing file: {e}")
            return "Error processing file", 400
    return render_template('home.html', error_message="No file uploaded.")

@app.route('/add_room_names', methods=['POST'])
def add_room_names():
    """Add names to unnamed rooms"""
    global stored_floorplan_data
    if not stored_floorplan_data:
        return "No floorplan data found", 400

    # Recompute unnamed_rooms
    unnamed_rooms = [idx for idx, area in enumerate(stored_floorplan_data['areas']) if not area.get('name')]

    for idx in unnamed_rooms:
        room_name = request.form.get(f'room_name_{idx}')
        if room_name == 'opening_room':
            opening_includes = request.form.get(f'opening_includes_{idx}')
            if opening_includes:
                opening_includes_list = opening_includes.split(',')
                stored_floorplan_data['areas'][int(idx)]['name'] = 'opening_space'
                stored_floorplan_data['areas'][int(idx)]['opening_includes'] = opening_includes_list
            else:
                # Handle the case where opening_includes is not provided
                return f"No opening includes provided for room {idx}", 400
        else:
            stored_floorplan_data['areas'][int(idx)]['name'] = room_name

    return redirect(url_for('options'))

@app.route('/options', methods=['GET', 'POST'])
def options():
    """Display options for the user to select the renovation type"""
    if request.method == 'POST':
        selected_option = request.form.get('option')
        print(f"Selected option: {selected_option}")
        if selected_option in ['option1', 'option2', 'option3', 'option4']:
            return redirect(url_for(f'process_{selected_option}'))
        else:
            return "Invalid option selected", 400

    # Pass the floorplan_data to the template if available
    if stored_floorplan_data:
        return render_template('options.html', floorplan_data=stored_floorplan_data)
    else:
        return render_template('options.html')


@app.route('/process_option1', methods=['GET', 'POST'])
def process_option1():
    """Process Option 1: Review a floorplan in its entirety"""
    indices = [i for i in range(len(stored_floorplan_data['areas']))]
    job_id = process_floorplan(indices)
    if isinstance(job_id, dict):
        return jsonify(job_id)  # Return error if job_id is actually an error message
    return redirect(url_for('result', job_id=job_id))

@app.route('/process_option2', methods=['GET', 'POST'])
def process_option2():
    """Process Option 2: Review just a part of the floorplan"""
    global stored_floorplan_data
    if request.method == 'POST':
        selected_indices = request.form.get('selected_indices')
        try:
            selected_indices = json.loads(selected_indices)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return jsonify({"message": f"JSON decode error: {str(e)}"})

        job_id = process_floorplan(selected_indices)
        if isinstance(job_id, dict):
            return jsonify(job_id)  # Return error if job_id is actually an error message
        return redirect(url_for('result', job_id=job_id))
    return render_template(
        'init_floorplan.html',
        floorplan_data=stored_floorplan_data,
        selected_option='option2',
        all_room_types=ALL_ROOM_TYPES  # Pass all_room_types if needed
    )

@app.route('/process_option3', methods=['GET', 'POST'])
def process_option3():
    """Process Option 3: Fill an empty space with just the exterior walls"""
    global stored_floorplan_data
    if request.method == 'POST':
        rooms_to_add_input = request.form.get('add_rooms', '')
        rooms_to_add = rooms_to_add_input.split(',')
        rooms_to_add = [room.strip() for room in rooms_to_add if room.strip()]
        
        # Initialize the add_list
        add_list = []
        
        # Since renovate_id_set is [0], we check if area[0] is 'opening_space'
        area = stored_floorplan_data['areas'][0]
        if area.get('name') == 'opening_space':
            opening_includes_list = area.get('opening_includes', [])
            print(f"Opening includes for opening_space at index 0: {opening_includes_list}")
            add_list.extend(opening_includes_list)
        
        # Also add rooms specified by the user
        add_list.extend(rooms_to_add)
        
        # Print the add_list before adding it to result_json
        print(f"Rooms to add: {add_list}")
        
        result_json = {
            "data": stored_floorplan_data,
            "renovate_id_set": [0],
            "renovate_change": {
                "delete": [],
                "add": add_list
            }
        }
        job_id = call_lambda_async(result_json)
        if isinstance(job_id, dict):
            return jsonify(job_id)  # Return error if job_id is actually an error message
        return redirect(url_for('result', job_id=job_id))
    return render_template(
        'init_floorplan.html',
        floorplan_data=stored_floorplan_data,
        selected_option='option3',
        all_room_types=ALL_ROOM_TYPES  # Pass all_room_types if needed
    )

@app.route('/process_option4', methods=['GET', 'POST'])
def process_option4():
    """Process Option 4: Fill an empty space in a section of the floorplan"""
    global stored_floorplan_data
    if request.method == 'POST':
        selected_indices = request.form.get('selected_indices')
        rooms_to_add_input = request.form.get('add_rooms', '')
        rooms_to_add = rooms_to_add_input.split(',')
        rooms_to_add = [room.strip() for room in rooms_to_add if room.strip()]
        try:
            selected_indices = json.loads(selected_indices)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return jsonify({"message": f"JSON decode error: {str(e)}"})

        # Initialize the add_list
        add_list = []
        
        # Iterate over the selected indices
        for idx in selected_indices:
            area = stored_floorplan_data['areas'][int(idx)]
            if area.get('name') == 'opening_space':
                opening_includes_list = area.get('opening_includes', [])
                print(f"Opening includes for opening_space at index {idx}: {opening_includes_list}")
                add_list.extend(opening_includes_list)
        
        # Also add rooms specified by the user
        add_list.extend(rooms_to_add)
        
        # Print the add_list before adding it to result_json
        print(f"Rooms to add: {add_list}")
        
        result_json = {
            "data": stored_floorplan_data,
            "renovate_id_set": selected_indices,
            "renovate_change": {
                "delete": [],
                "add": add_list
            }
        }
        job_id = call_lambda_async(result_json)
        if isinstance(job_id, dict):
            return jsonify(job_id)  # Return error if job_id is actually an error message
        return redirect(url_for('result', job_id=job_id))
    return render_template(
        'init_floorplan.html',
        floorplan_data=stored_floorplan_data,
        selected_option='option4',
        all_room_types=ALL_ROOM_TYPES  # Pass all_room_types if needed
    )

def process_floorplan(indices):
    """Common processing function for floorplans"""
    global stored_floorplan_data
    result_json = {
        "data": stored_floorplan_data,
        "renovate_id_set": indices,
        "renovate_change": {"delete": [], "add": []}
    }
    job_id = call_lambda_async(result_json)
    if isinstance(job_id, dict):
        return jsonify(job_id)  # Return error if job_id is actually an error message
    return job_id

def call_lambda_async(result_json):
    """Call AWS Lambda function asynchronously after saving the result JSON to S3."""
    job_id = str(int(time.time()))
    s3_key = f"optimizer/floorplans/{job_id}.json"

    # Debugging: Print the bucket name to confirm it is set correctly
    print(f"Using S3 bucket name: {S3_BUCKET_NAME}")

    # Upload JSON to S3
    try:
        # Check if the bucket name is valid
        if not S3_BUCKET_NAME or '/' in S3_BUCKET_NAME:
            raise ValueError("Invalid S3 bucket name: Bucket name cannot be empty or contain '/' or other invalid characters.")
        
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=json.dumps(result_json))
        print(f"Uploaded JSON to S3 with key: {s3_key}")
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        return {"message": "Failed to upload to S3", "error": str(e)}

    # Invoke the processing Lambda function asynchronously
    try:
        response = lambda_client.invoke(
            FunctionName='optimizer-poc-async-job-completion-notifier',  
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({'bucket': S3_BUCKET_NAME, 'key': s3_key, 'job_id': job_id})
        )
        print(f"Generation Lambda invoked asynchronously with job ID {job_id}")
        return job_id
    except Exception as e:
        print(f"Error invoking Lambda: {e}")
        return {"message": "Failed to invoke Lambda", "error": str(e)}

@app.route('/check_status/<job_id>', methods=['GET'])
def check_status(job_id):
    """Check the status of the job by reading from the SQS queue."""
    try:
        print(f"Checking status for job_id: {job_id}")  # Debug: Log job ID being checked
        response = sqs_client.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=10,  # Increased to check multiple messages
            WaitTimeSeconds=0
        )
        if 'Messages' in response:
            for message in response['Messages']:
                body = json.loads(message['Body'])
                if job_id == body.get('job_id'):
                    # Job found, return the result
                    print(f"Job {job_id} found in SQS. Deleting message and returning result.")  # Debug: Log job match found
                    sqs_client.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    return jsonify({"status": "complete", "result": body.get('result', 'No result found')})
                else:
                    print(f"Job {job_id} not found in this message, checking next.")  # Debug: Log job not found in the current message
            print(f"Job {job_id} not found in SQS messages.")  # Debug: Log after checking all messages
            return jsonify({"status": "in progress"})
        else:
            print("No messages in SQS queue.")  # Debug: Log if no messages are found in SQS
            return jsonify({"status": "in progress"})

    except Exception as e:
        print(f"Error while checking status: {e}")  # Debug: Log any exceptions
        return jsonify({"status": "error", "message": str(e)})

@app.route('/result', methods=['GET'])
def result():
    """Display the final floorplan result without interaction"""
    job_id = request.args.get('job_id')
    if not job_id:
        return "Job ID not provided", 400

    global stored_floorplan_data
    if not stored_floorplan_data:
        return "No original floorplan data found", 400

    # Pass the original floorplan data to the template
    return render_template('result.html', job_id=job_id, original_floorplan_data=stored_floorplan_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
