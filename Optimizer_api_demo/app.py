from flask import Flask, request, jsonify, render_template
import json
import boto3
import os

app = Flask(__name__)

# Store the floorplan_data in a global variable or use a session to store it for the user.
stored_floorplan_data = None
# Initialize the boto3 Lambda client
lambda_client = boto3.client('lambda', region_name='ca-central-1')


@app.route('/', methods=['GET', 'POST'])
def index():
    global stored_floorplan_data
    if request.method == 'POST':
        file = request.files.get('floorplanner_plan')
        if file:
            try:
                # Read the uploaded file and decode it
                data = file.read().decode('utf-8')
                # Load the JSON data
                stored_floorplan_data = json.loads(data)
                print('Loaded floorplan_data keys:', stored_floorplan_data.keys())
                # Pass the JSON data to the template
                return render_template('index.html', floorplan_data=stored_floorplan_data)
            except Exception as e:
                print(f"Error processing file: {e}")
                return "Error processing file", 400
    # If GET request, render the template with no data
    return render_template('index.html', floorplan_data=None)


@app.route('/submit', methods=['POST'])
def submit():
    global stored_floorplan_data
    # Check if we have stored floorplan data
    if not stored_floorplan_data:
        return "No floorplan data found", 400

    # Print the raw data for debugging
    print("Request submission")
    
    selected_indices = request.form.get('selected_indices')
    action = request.form.get('renovate_action')

    print(f"Selected indices received: {selected_indices}")
    print(f"Renovation action: {action}")
    
    try:
        # Parse the received JSON data
        selected_indices = json.loads(selected_indices)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return f"JSON decode error: {str(e)}"

    # Prepare the renovation change data
    renovate_change = {
        "delete": [],
        "add": []
    }

    if action == 'add_rooms':
        rooms_to_add = request.form.get('add_rooms').split(',')
        renovate_change['add'] = [room.strip() for room in rooms_to_add]
    elif action == 'delete_room':
        renovate_change['delete'] = selected_indices

    # Create the final result JSON
    result_json = {
        "data": stored_floorplan_data,  # Use the stored floorplan data
        "renovate_id_set": selected_indices,
        "renovate_change": renovate_change
    }

    # Print the result JSON to the console
    # print(json.dumps(result_json, indent=4))
    file_path = os.path.join(os.getcwd(), 'optimizer_input.json')
    with open(file_path, 'w') as f:
        json.dump(result_json, f, indent=4)
    
    print(f"Saved result JSON to {file_path}")

    try:
        # Invoke the Lambda function using the full name
        response = lambda_client.invoke(
            FunctionName='dev-asyncPlanGenStack-OptimizerFunction-pvcuXetLNgvZ',
            InvocationType='RequestResponse',
            Payload=json.dumps(result_json)
        )

        # Read and decode the response payload
        response_payload = response['Payload'].read().decode('utf-8')
        response_payload = json.loads(response_payload)  # Convert to dictionary

        # Check if the 'body' key exists and is itself a JSON string
        if isinstance(response_payload, dict) and 'body' in response_payload:
            response_body = json.loads(response_payload['body'])
            if "response" in response_body and "floors" in response_body["response"]:
                areas = response_body["response"]["floors"][0]['designs'][0]['areas']
                print(f"areas is {areas}")
                return render_template('index.html', floorplan_data=stored_floorplan_data, areas=areas)
            else:
                print("Lambda function returned unexpected data")
                return render_template('index.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: unexpected response from the Lambda function.")
        else:
            print("Lambda function returned unexpected data format")
            return render_template('index.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: unexpected response format from the Lambda function.")
    
    except Exception as e:
        print(f"Error invoking Lambda: {str(e)}")
        return render_template('index.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: could not process the request.")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

