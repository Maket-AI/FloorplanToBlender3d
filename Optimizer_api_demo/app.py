from flask import Flask, request, jsonify, render_template, redirect, url_for
import json
import boto3
import os
import time  # Import the time module
from botocore.config import Config

app = Flask(__name__)

stored_floorplan_data = None
config = Config(connect_timeout=5, read_timeout=300)  # 5 seconds for connection, 900 seconds for reading
lambda_client = boto3.client('lambda', region_name='ca-central-1', config=config)


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
                # If there are unnamed rooms, prompt user to add room names
                return render_template('init_floorplan.html', floorplan_data=stored_floorplan_data, unnamed_rooms=unnamed_rooms)

            # If all rooms have names, redirect to options page
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

    room_names = request.form.getlist('room_name')
    unnamed_rooms = request.form.getlist('room_index')

    for idx, room_name in zip(unnamed_rooms, room_names):
        stored_floorplan_data['areas'][int(idx)]['name'] = room_name

    # After adding room names, redirect to options page
    return redirect(url_for('options'))

@app.route('/options', methods=['GET', 'POST'])
def options():
    """Display options for the user to select the renovation type"""
    if request.method == 'POST':
        selected_option = request.form.get('option')
        print(f"Selected option: {selected_option}")
        if selected_option == 'option1':
            return redirect(url_for('process_option1'))
        elif selected_option == 'option2':
            return redirect(url_for('process_option2'))
        elif selected_option == 'option3':
            return redirect(url_for('process_option3'))
        elif selected_option == 'option4':
            return redirect(url_for('process_option4'))
        else:
            return "Invalid option selected", 400
    
    # Render the options page
    return render_template('options.html')

@app.route('/process_option1', methods=['GET', 'POST'])
def process_option1():
    """Process Option 1: Review a floorplan in its entirety"""
    global stored_floorplan_data
    indices = list(range(len(stored_floorplan_data['areas'])))
    result_json = {
        "data": stored_floorplan_data,
        "renovate_id_set": indices,
        "renovate_change": {
            "delete": [],
            "add": []
        }
    }
    return call_lambda(result_json)

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
            return f"JSON decode error: {str(e)}"

        result_json = {
            "data": stored_floorplan_data,
            "renovate_id_set": selected_indices,
            "renovate_change": {
                "delete": [],
                "add": []
            }
        }
        return call_lambda(result_json)
    # Render without the option selection
    return render_template('init_floorplan.html', floorplan_data=stored_floorplan_data, selected_option='option2')


@app.route('/process_option3', methods=['GET', 'POST'])
def process_option3():
    """Process Option 3: Fill an empty space with just the exterior walls"""
    global stored_floorplan_data
    if request.method == 'POST':
        rooms_to_add = request.form.get('add_rooms').split(',')
        result_json = {
            "data": stored_floorplan_data,
            "renovate_id_set": [0],
            "renovate_change": {
                "delete": [],
                "add": [room.strip() for room in rooms_to_add]
            }
        }
        return call_lambda(result_json)
    # Directly select all rooms for this option
    return render_template('init_floorplan.html', floorplan_data=stored_floorplan_data, selected_option='option3')

@app.route('/process_option4', methods=['GET', 'POST'])
def process_option4():
    """Process Option 4: Fill an empty space in a section of the floorplan"""
    global stored_floorplan_data
    if request.method == 'POST':
        selected_indices = request.form.get('selected_indices')
        rooms_to_add = request.form.get('add_rooms').split(',')
        try:
            selected_indices = json.loads(selected_indices)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return f"JSON decode error: {str(e)}"

        result_json = {
            "data": stored_floorplan_data,
            "renovate_id_set": selected_indices,
            "renovate_change": {
                "delete": [],
                "add": [room.strip() for room in rooms_to_add]
            }
        }
        return call_lambda(result_json)
    return render_template('init_floorplan.html', floorplan_data=stored_floorplan_data, selected_option='option4')


def call_lambda(result_json):
    """Call AWS Lambda function with the result JSON and save it locally"""
    # Save the result JSON to a local file
    try:
        start_time = time.time()  # Start time measurement

        with open('result_json_backup.json', 'w') as file:
            json.dump(result_json, file, indent=4)
        print("Result JSON saved locally as 'result_json_backup.json'.")

        # Proceed to call the Lambda function
        print("Calling Lambda with result JSON:", result_json)
        response = lambda_client.invoke(
            FunctionName='dev-asyncPlanGenStack-OptimizerFunction-pvcuXetLNgvZ',
            InvocationType='RequestResponse',
            Payload=json.dumps(result_json)
        )

        response_payload = response['Payload'].read().decode('utf-8')
        response_payload = json.loads(response_payload)

        end_time = time.time()  # End time measurement
        runtime = end_time - start_time
        print(f"Lambda invocation runtime: {runtime:.2f} seconds.")  # Print the runtime

        if isinstance(response_payload, dict) and 'body' in response_payload:
            response_body = json.loads(response_payload['body'])
            if "response" in response_body and "floors" in response_body["response"]:
                areas = response_body["response"]["floors"][0]['designs'][0]['areas']
                print(f"Areas are: {areas}")
                return redirect(url_for('result', areas=json.dumps(areas)))
            else:
                return render_template('submit.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: unexpected response from the Lambda function.")
        else:
            return render_template('submit.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: unexpected response format from the Lambda function.")

    except Exception as e:
        print(f"An error occurred: {e}")
        return render_template('submit.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: could not process the request.")


@app.route('/result', methods=['GET'])
def result():
    """Display the final floorplan result without interaction"""
    areas = request.args.get('areas')
    if areas:
        areas = json.loads(areas)
        return render_template('result.html', areas=areas)
    else:
        return "No areas data available", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
