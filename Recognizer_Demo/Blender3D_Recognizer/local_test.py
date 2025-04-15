import sys
import os
from detector import detect_floorplan_image
import boto3
from urllib.parse import urlparse, unquote
import json
from app import lambda_handler
lambda_client = boto3.client("lambda")
floorplan_lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
try:
    sys.path.insert(0, floorplan_lib_path)
    from FloorplanToBlenderLib import *  # floorplan to blender lib
except ImportError:
    from FloorplanToBlenderLib import *  # floorplan to blender lib
from subprocess import check_output

def local_test(image_url=None):
    print(floorplan_lib_path)

    image_names = ["example_simple.jpg"]
    for image_name in image_names:
        input_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../events/", image_name))
        save_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__),"outputs", f"detected_{image_name}"))
        # Call the processing function with adjusted parameters
        detect_floorplan_image(
            input_image_path, 
            save_image_path, 
            lambda_client, 
            image_url
        )
    

def process_batch_test(bucket_name, prefix):
    # Initialize the S3 client
    s3 = boto3.client('s3')

    # List files in the specific S3 bucket and prefix
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    # Extract file names from the response
    files = [item['Key'] for item in response.get('Contents', [])]

    # Initialize a dictionary to store the file names and paths
    paths_dict = {}

    for file_key in files:
        # Check file extension
        file_extension = file_key.lower().split('.')[-1]
        if file_extension not in ['jpg', 'jpeg', 'png']:
            # Skip files that are not in the desired format
            print(f"Skipping file {file_key} as it is not a JPEG, PNG, or JPG.")
            continue

        # Construct the file URL
        file_url = f"https://{bucket_name}.s3.ca-central-1.amazonaws.com/{file_key}"
        
        # Create an event for the lambda handler
        event = {"image_url": file_url}
        
        # Call the lambda handler
        response = lambda_handler(event, "")
        body = json.loads(response['body'])
        # Access the 'paths' key in the response
        if 'paths' in body:
            paths_dict[file_key] = body['paths']
        else:
            paths_dict[file_key] = ["No paths found in response."]
    
    return paths_dict


def s3_test(img_url=None):
    if img_url != None:
        event = {
            "image_url": img_url
        }
        response = lambda_handler(event, "")
        # print(f"s3_test{response}")
        return 
    
    paths = []
    image_file = ['test_1.png', 'test_2.png', 'test_3.jpg', 'test_4.jpg', 'test_5.png', 'test_6.jpeg']
    image_file = ['test_5.png']
    image_file = ['test_2.png']
    print('start')
    for image_name in image_file:
        event = {
            "image_url": f"https://floorplan-detector.s3.ca-central-1.amazonaws.com/2024-01-03/{image_name}"
        }
        response = lambda_handler(event, "")
        # print(f"s3_test{response}")


if __name__ == "__main__":
    # paths_dict = process_batch_test('floorplan-detector', 'test_dataset/standard/')
    # print(f"final response: {paths_dict}")
    image_name = "21_52_00-plan_0-B_21_52_36.jpg"
    # Set up the image URL for local testing
    image_url = f"https://floorplan-detector.s3.ca-central-1.amazonaws.com/test_dataset/{image_name}"
    local_test(image_url)