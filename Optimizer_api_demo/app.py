from flask import Flask, request, jsonify, render_template
import json

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('floorplanner_plan')
        if file:
            data = file.read().decode('utf-8')
            json_data = json.loads(data)
            print('floorplan_data:', json_data.keys())  # Confirm data is being loaded
            return render_template('index.html', floorplan_data=json_data)
    return render_template('index.html', floorplan_data=None)


@app.route('/submit', methods=['POST'])
def submit():
    # Print the raw data for debugging
    print("Request submission")
    
    raw_data = request.form.get('data')
    selected_indices = request.form.get('selected_indices')
    action = request.form.get('renovate_action')

    print(f"Raw data received: {raw_data}")
    print(f"Selected indices received: {selected_indices}")
    print(f"Renovation action: {action}")
    
    try:
        data = json.loads(raw_data)
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
        "data": data,
        "renovate_id_set": selected_indices,
        "renovate_change": renovate_change
    }

    # Print the JSON to the console
    print(json.dumps(result_json, indent=4))

    # Save the JSON to a file
    with open('renovation_output.json', 'w') as f:
        json.dump(result_json, f, indent=4)

    return jsonify(result_json)

if __name__ == '__main__':
    app.run(debug=True)
