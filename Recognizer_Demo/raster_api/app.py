from flask import Flask, request, render_template, jsonify
from flask_cors import CORS
import os
import base64
import requests
import json
from PIL import Image
import io
import numpy as np
import math
from dotenv import load_dotenv
from io import BytesIO
import logging
import socket

# Import the processing functions from the new module
from process_results_from_raster import (
    ElementProcessor,
    DoorDetector,
    BoundaryCalculator,
    GeometryHelper,
    MeasurementGenerator
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Get API credentials from environment variables
API_KEY = os.environ.get("RAPIDAPI_KEY", "b7c406c722mshbd9563256cc9954p1fc084jsn50461ade5253")
API_HOST = "floor-plan-digitalization.p.rapidapi.com"
API_URL = f"https://{API_HOST}/raster-to-vector-base64"

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Use DoorDetector's static method for find_potential_doors
find_potential_doors = DoorDetector.find_potential_doors

def process_floorplan(image_data):
    """Process floor plan image using the RapidAPI."""
    try:
        # First, try to resolve the API host to check connectivity
        try:
            socket.gethostbyname(API_HOST)
        except socket.gaierror as e:
            logger.error(f"DNS resolution failed for {API_HOST}: {str(e)}")
            return {"error": f"Unable to resolve API host: {str(e)}"}

        # Get API key from environment variable
        api_key = API_KEY
        if not api_key:
            logger.error("API key not found in environment variables")
            return {"error": "API key not configured"}

        headers = {
            "Content-Type": "application/json",
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": API_HOST
        }
        
        # Prepare the request payload
        payload = {
            "image": image_data
        }
        
        # Make the API request with timeout and retries
        session = requests.Session()
        retries = requests.adapters.Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
        
        logger.debug(f"Sending request to {API_URL}")
        response = session.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=30  # 30 seconds timeout
        )
        
        logger.debug(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.debug(f"API response: {json.dumps(result, indent=2)}")
            
            # Check if the response has the expected structure
            if not isinstance(result, dict):
                logger.error(f"Unexpected response format: {result}")
                return {"error": "Unexpected response format from API"}
                
            # Ensure the response has the required fields
            if "rooms" not in result:
                logger.warning("Response does not contain 'rooms' field")
                result["rooms"] = []
            else:
                logger.debug(f"Rooms structure: {type(result['rooms'])}, count: {len(result['rooms'])}")
                
            if "walls" not in result:
                logger.warning("Response does not contain 'walls' field")
                result["walls"] = []
            else:
                logger.debug(f"Walls structure: {type(result['walls'])}, count: {len(result['walls'])}")
                
            if "doors" not in result:
                logger.warning("Response does not contain 'doors' field")
                # Create sample doors based on walls for testing if needed
                result["doors"] = []
                # Find potential door locations at wall gaps
                if len(result.get("walls", [])) > 0:
                    potential_doors = find_potential_doors(result["walls"])
                    if potential_doors:
                        result["doors"] = potential_doors
                        logger.debug(f"Generated {len(potential_doors)} potential doors")
            else:
                logger.debug(f"Doors structure: {type(result['doors'])}, count: {len(result['doors'])}")
                
            # Create a copy of the result without the base64 image data
            result_to_save = result.copy()
            if "image" in result_to_save:
                del result_to_save["image"]
            
            # Save the result to a JSON file
            output_file = os.path.join(OUTPUT_FOLDER, 'example_simple_result.json')
            with open(output_file, 'w') as f:
                json.dump(result_to_save, f, indent=2)
            logger.debug(f"Saved API response to {output_file}")
                
            # Process the results to make them ready for frontend rendering
            processed_result = ElementProcessor.process_result_for_frontend(result)
            
            # Log the processed result structure for debugging
            logger.debug(f"Processed doors: {len(processed_result.get('doors', []))}")
            for i, door in enumerate(processed_result.get('doors', [])):
                logger.debug(f"Door {i}: position={door.get('position')}, wallId={door.get('wallId')}, width={door.get('width')}")
            
            logger.debug(f"Processed windows: {len(processed_result.get('windows', []))}")
            for i, window in enumerate(processed_result.get('windows', [])):
                logger.debug(f"Window {i}: position={window.get('position')}, wallId={window.get('wallId')}, width={window.get('width')}")
            
            return processed_result
        elif response.status_code == 403:
            error_msg = "API access forbidden. Please check your API key."
            logger.error(error_msg)
            return {"error": error_msg}
        else:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {"error": error_msg}
            
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}
    except requests.exceptions.Timeout as e:
        error_msg = f"Request timeout: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error during API request: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save the uploaded file
        filename = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filename)
        logger.debug(f"Saved uploaded file to {filename}")
        
        # Read the saved file and encode it
        with open(filename, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Process the floor plan
        result = process_floorplan(image_data)
        
        if 'error' in result:
            return jsonify(result), 400
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/floorplan-data')
def get_floorplan_data():
    # Try to load the most recent floor plan data from the output file
    try:
        output_file = os.path.join(OUTPUT_FOLDER, 'example_simple_result.json')
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({'error': 'No floor plan data available'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True) 