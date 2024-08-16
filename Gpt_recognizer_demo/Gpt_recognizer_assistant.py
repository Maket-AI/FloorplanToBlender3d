from openai import OpenAI
from dotenv import load_dotenv
import os
import json

# Load environment variables from .env file
load_dotenv()

# Fetch the API key from environment variable
api_key = os.getenv("OPENAI_API_KEY")
if api_key is None:
    raise ValueError("API key is not set in the environment variables")

# Initialize the client with your API key
client = OpenAI(api_key=api_key)

def create_assistant(client, model_name="gpt-4-turbo"):
    try:
        virtual_architect = client.beta.assistants.create(
            description="A comprehensive assistant for floor plan recognizer.",
            instructions="""
                You are a comprehensive assistant named 'Virtual Floorplan Recognizer Master' designed to help with recognizing a floorplan image and provide the correct information. You have the ability to:

                1. **Recognize Floor Plans from Images**: Take an image URL and extract the floor plan details such as room dimensions, positions, and room types.

                2. **Generate Floor Plans**: Convert a text prompt describing a floorplan into a JSON data format.

                ### Recognizing Floor Plans from Images
                When given the input "can you recognize this floorplan by giving the room's dimensions and positions, and the room_type?" followed by an image URL, extract the floorplan details and provide them in a structured format.

                ### Generating Floor Plans from Text
                When given a text prompt describing a floorplan, generate a JSON floor plan without asking for additional clarification.
                
                If there are no specific dimensions provided, use default values based on typical room sizes.
                If there is only one floor, assume it is the ground floor unless otherwise specified.

                The structure for the JSON output should be:
                {
                    "prompt": "<The original text prompt used to generate the floor plan>",
                    "floors": [
                        {
                            "areas": [
                                {
                                    "color": "#DDDDDD",
                                    "showAreaLabel": true,
                                    "poly": [
                                        {"x": <position of a room's vertex, in cm>, "y": <position of a room's vertex, in cm>}
                                    ]
                                }
                            ],
                            "walls": [
                                {
                                    "a": {"x": <begin point of a wall's position x, in cm>, "y": <begin point of a wall's position y, in cm>},
                                    "b": {"x": <end point of a wall's position x, in cm>, "y": <end point of a wall's position y, in cm>},
                                    "c": "None",
                                    "az": {"z": 0, "h": 280},
                                    "bz": {"z": 0, "h": 280},
                                    "thickness": 12,
                                    "balance": 0.5,
                                    "decor": {
                                        "left": {"color": "#F2EAD7"},
                                        "right": {"color": "#F2EAD7"},
                                        "top": "None",
                                        "outline": 0
                                    },
                                    "openings": [
                                        {
                                            "refid": "<refid_type: { 'doors': '200', 'windows': '219', 'exterior_doors': '210', 'garage_door': '222' }>",
                                            "t": <float number, 0..1 - relative position of the opening on the wall>,
                                            "type": "<string, door or window>",
                                            "width": <int, the width of this opening>,
                                            "z_height": 220,
                                            "z": 0,
                                            "mirrored": [0, 1] // vertical and horizontal flipping
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            """,

            name="Virtual architect",
            tools=[{"type": "code_interpreter"}],
            model=model_name,
        )
        print("Assistant created successfully.")
        return virtual_architect
    except Exception as e:
        print("Failed to create the assistant.")
        print("Error:", str(e))

def use_assistant(client, assistant_id, prompt):
    print(f"Using assistant {assistant_id} to interpret the prompt.")
    response = []

    try:
        # Use the assistant to generate a response
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=300,
        )
        
        # Print the response for debugging
        print("Response from assistant:", response)

        # Access the response content correctly
        if response.choices:
            content = response.choices[0].message.content
            print("Assistant response:", content)
            return json.loads(content)  # Assuming the assistant returns JSON formatted string
        else:
            print("No choices returned in response.")
            return {"error": "No choices returned in response."}
    except Exception as e:
        print("Failed to run the semi-live mode.")
        print("Error:", str(e))
        return {"error": "Failed to generate floor plan JSON."}


# Define the image URL for testing
image_url = "https://wpmedia.roomsketcher.com/content/uploads/2022/01/06145940/What-is-a-floor-plan-with-dimensions.png"

# Define the prompt
prompt = f"Can you recognize this floorplan by giving the room's dimensions, positions, and room_type in JSON format? in this image {image_url}"

# Create the assistant and use it to process the image and generate the JSON floor plan
virtual_architect = create_assistant(client)
assistant_id = virtual_architect.id

floor_plan_json = use_assistant(client, assistant_id, prompt)

# Print the results
print("Generated Floor Plan JSON:")
print(json.dumps(floor_plan_json, indent=2))
