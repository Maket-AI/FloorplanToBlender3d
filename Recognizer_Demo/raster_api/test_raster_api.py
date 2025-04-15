#!/usr/bin/env python3
import os
import sys
import json
import requests
import argparse
import base64
from pathlib import Path

def test_floor_plan_digitalization(image_path, output_dir=None):
    """
    Test the floor plan digitalization API with a given image.
    
    Args:
        image_path (str): Path to the input image
        output_dir (str, optional): Directory to save the output. Defaults to None.
    
    Returns:
        dict: API response
    """
    # API endpoint
    url = "https://floor-plan-digitalization.p.rapidapi.com/raster-to-vector-base64"
    
    # Get API key from environment variable or use a default
    api_key = os.environ.get("RAPIDAPI_KEY", "b7c406c722mshbd9563256cc9954p1fc084jsn50461ade5253")
    
    # Headers for the API request
    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "floor-plan-digitalization.p.rapidapi.com"
    }
    
    # Read and encode the image as base64
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Prepare the request payload
    payload = {
        "image": image_data
    }
    
    # Make the API request
    response = requests.post(url, headers=headers, json=payload)
    
    # Check if the request was successful
    if response.status_code == 200:
        result = response.json()
        
        # Save the result to a JSON file if output directory is provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{Path(image_path).stem}_result.json")
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Result saved to {output_file}")
        
        return result
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def main():
    parser = argparse.ArgumentParser(description='Test the floor plan digitalization API')
    parser.add_argument('--image', type=str, help='Path to the input image')
    parser.add_argument('--output', type=str, help='Directory to save the output')
    parser.add_argument('--api-key', type=str, help='RapidAPI key')
    args = parser.parse_args()
    
    # If API key is provided, set it as an environment variable
    if args.api_key:
        os.environ["RAPIDAPI_KEY"] = args.api_key
    
    # If no image is provided, use a default image from the events directory
    if not args.image:
        events_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../events"))
        args.image = os.path.join(events_dir, "example_simple.jpg")
    
    # If no output directory is provided, use a default directory
    if not args.output:
        args.output = os.path.abspath(os.path.join(os.path.dirname(__file__), "outputs"))
    
    print(f"Processing image: {args.image}")
    result = test_floor_plan_digitalization(args.image, args.output)
    
    if result:
        print("API call successful!")
        print(f"Number of rooms detected: {len(result.get('rooms', []))}")
    else:
        print("API call failed!")

if __name__ == "__main__":
    main() 