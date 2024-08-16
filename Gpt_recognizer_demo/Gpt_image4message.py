from openai import OpenAI
import json
client = OpenAI()

instructions = """
You need to recognize an image-based floorplan and provide detailed information about the rooms, including their positions, types, and areas. You have the ability to:

1. **Describe the Floorplan**: Identify and describe each room by its type, the coordinates of its center point, and its area in square meters. The room types should match one of the following:
    - living_room
    - kitchen
    - dining_room
    - corridor
    - entry
    - bedroom
    - bathroom
    - garage
    - laundry_room
    - mudroom
    - stair
    - deck
    - closet
    - walk-in

2. **Provide Position Information of Each Room**: Extract the floor plan details such as room dimensions, positions, and room types from the given image URL.

### Recognizing Floor Plans from Images
When given the input "can you recognize this floorplan to give the room's dimensions and positions, and the room_type?" followed by an image URL, extract the floorplan details and provide them in a structured format.

The structure for the JSON output should be:
{
    "prompt": "<The original text prompt used to generate the floor plan>",
    "floors": [
        {
            "areas": [
                {
                    "room_type": "<type of the room>",
                    "area": "<area of the room in sq meters>",
                    "center_point": {"x": <center x coordinate>, "y": <center y coordinate>},
                    "poly": [
                        {"x": <position of a room's vertex, in cm>, "y": <position of a room's vertex, in cm>},
                        {"x": <position of a room's vertex, in cm>, "y": <position of a room's vertex, in cm>},
                        {"x": <position of a room's vertex, in cm>, "y": <position of a room's vertex, in cm>},
                        {"x": <position of a room's vertex, in cm>, "y": <position of a room's vertex, in cm>}
                    ],
                    "color": "#DDDDDD",
                    "showAreaLabel": true
                }
            ]
        }
    ]
}

In the final result, you mainly generate json format with "floors" but short and cut description. 
"""
image_url = "https://wpmedia.roomsketcher.com/content/uploads/2022/01/06145940/What-is-a-floor-plan-with-dimensions.png"
image_url = "https://static.getasiteplan.com/uploads/2022/11/basic-floor-plan.jpg"
response = client.chat.completions.create(
  model="gpt-4o",
  messages=[
    {
        "role": "system",
        "content": instructions
    },
    {
        "role": "user",
        "content": [
        {"type": "text", "text": f"Can you recognize this floorplan to give the room's dimensions and positions, and the room_type? Here is the image URL: {image_url}"},
        {
          "type": "image_url",
          "image_url": {
            "url": image_url,
          },
        },
      ],
    }
  ],
  max_tokens=1500,
)

# print(type(response.choices[0]))
# print(response.choices[0])


# Correctly access the content
response_message = response.choices[0].message.content

# Save the extracted JSON content to a file
with open('floorplan.json', 'w') as json_file:
    json_file.write(response_message)

print("JSON output has been saved to floorplan.json")