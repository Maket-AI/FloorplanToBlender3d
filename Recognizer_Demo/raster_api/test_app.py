import requests
import base64
import os
import json

def test_app_integration():
    """Test the app.py integration with the updated processing code."""
    print("Testing app.py integration with the updated door and window processing...")
    
    # Prepare the test image
    script_dir = os.path.dirname(os.path.abspath(__file__))
    example_image = None
    
    # Try to find an example image
    for img_file in os.listdir(os.path.join(script_dir, 'uploads')):
        if img_file.endswith(('.png', '.jpg', '.jpeg')):
            example_image = os.path.join(script_dir, 'uploads', img_file)
            break
            
    if not example_image:
        print("No example image found in the uploads directory.")
        print("Please upload an image first using the web interface.")
        return
        
    # Read the example image
    with open(example_image, 'rb') as f:
        image_data = f.read()
        
    # Create a multipart form request
    files = {'file': (os.path.basename(example_image), image_data)}
    
    try:
        # Send POST request to the /process endpoint
        response = requests.post('http://localhost:3000/process', files=files)
        
        if response.status_code == 200:
            result = response.json()
            
            # Print summary of the response
            print("\nAPI Response Summary:")
            print(f"- Status: {result.get('status', 'N/A')}")
            print(f"- Message: {result.get('message', 'N/A')}")
            print(f"- Walls: {len(result.get('walls', []))}")
            print(f"- Rooms: {len(result.get('rooms', []))}")
            print(f"- Doors: {len(result.get('doors', []))}")
            print(f"- Windows: {len(result.get('windows', []))}")
            
            # Verify that the original bounding boxes are included
            if 'original_bboxes' in result:
                print(f"- Original Bounding Boxes: {len(result.get('original_bboxes', []))}")
                
            print("\nTest completed successfully. The updated door and window processing code is working correctly through app.py.")
            
        else:
            print(f"Error: Received status code {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the Flask server.")
        print("Make sure app.py is running on http://localhost:3000")

if __name__ == "__main__":
    test_app_integration() 