from flask import Flask, request, jsonify, render_template
import json

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        file = request.files.get('floorplanner_plan')
        room_type = request.form.get('room_type')
        action = request.form.get('renovate_action')
        renovate_change = {}

        if file:
            data = file.read().decode('utf-8')
            json_data = json.loads(data)
            renovate_id_set = []

            if action == 'add_rooms':
                rooms_to_add = request.form.get('add_rooms').split(',')
                renovate_change['add'] = [room.strip() for room in rooms_to_add]
            elif action == 'change_layout':
                # Implement change layout logic here
                pass
            elif action == 'delete_room':
                renovate_change['delete'] = room_type

            for index, area in enumerate(json_data["AREA"]):
                if action == 'delete_room' and area["type"] == room_type:
                    renovate_id_set.append(index)

            result_json = {
                "data": json_data,
                "renovate_id_set": renovate_id_set,
                "renovate_change": renovate_change
            }

            result = json.dumps(result_json, indent=4)

    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
