from flask import Flask, request, jsonify, render_template, redirect, url_for
import json
import boto3
import os

app = Flask(__name__)

stored_floorplan_data = None
lambda_client = boto3.client('lambda', region_name='ca-central-1')

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
                return render_template('init_floorplan.html', floorplan_data=stored_floorplan_data, unnamed_rooms=unnamed_rooms)

            return render_template('init_floorplan.html', floorplan_data=stored_floorplan_data)
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

    return render_template('init_floorplan.html', floorplan_data=stored_floorplan_data)

@app.route('/submit', methods=['POST'])
def submit():
    """Submit the renovated floorplan"""
    global stored_floorplan_data
    if not stored_floorplan_data:
        return "No floorplan data found", 400

    print("Request submission")

    selected_indices = request.form.get('selected_indices')
    action = request.form.get('renovate_action')

    print(f"Selected indices received: {selected_indices}")
    print(f"Renovation action: {action}")

    try:
        selected_indices = json.loads(selected_indices)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return f"JSON decode error: {str(e)}"

    renovate_change = {
        "delete": [],
        "add": []
    }

    if action == 'add_rooms':
        rooms_to_add = request.form.get('add_rooms').split(',')
        renovate_change['add'] = [room.strip() for room in rooms_to_add]
    elif action == 'delete_room':
        renovate_change['delete'] = selected_indices

    result_json = {
        "data": stored_floorplan_data,
        "renovate_id_set": selected_indices,
        "renovate_change": renovate_change
    }
    print("finish json")
    file_path = os.path.join(os.getcwd(), 'optimizer_input.json')
    with open(file_path, 'w') as f:
        json.dump(result_json, f, indent=4)

    print(f"Saved result JSON to {file_path}")

    try:
        response = lambda_client.invoke(
            FunctionName='dev-asyncPlanGenStack-OptimizerFunction-pvcuXetLNgvZ',
            InvocationType='RequestResponse',
            Payload=json.dumps(result_json)
        )

        response_payload = response['Payload'].read().decode('utf-8')
        response_payload = json.loads(response_payload)

        if isinstance(response_payload, dict) and 'body' in response_payload:
            response_body = json.loads(response_payload['body'])
            if "response" in response_body and "floors" in response_body["response"]:
                areas = response_body["response"]["floors"][0]['designs'][0]['areas']
                print(f"areas is {areas}")
                # Redirect to the result page after successful processing
                return redirect(url_for('result', areas=json.dumps(areas)))
            else:
                return render_template('submit.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: unexpected response from the Lambda function.")
        else:
            return render_template('submit.html', floorplan_data=stored_floorplan_data, error_message="Renovation failed: unexpected response format from the Lambda function.")

    except Exception as e:
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
