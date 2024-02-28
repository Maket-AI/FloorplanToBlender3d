
import sys
import os
from detector import detect_floorplan_image
import boto3
import tempfile
from urllib.parse import urlparse, unquote
import json

floorplan_lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
try:
    sys.path.insert(0, floorplan_lib_path)
    from FloorplanToBlenderLib import *  # floorplan to blender lib
except ImportError:
    from FloorplanToBlenderLib import *  # floorplan to blender lib
from subprocess import check_output


def lambda_handler(event, context):
    print(f"Master_Event: {event}")

    # Check if the function is invoked via API Gateway or directly
    if 'body' in event:
        # If invoked via API Gateway
        body = json.loads(event['body'])
        image_url = body.get('image_url', '')
    else:
        # If invoked directly
        image_url = event.get('image_url', '')

    if not image_url:
        print("No image_url provided")
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Missing image_url"})
        }

    parsed_url = urlparse(image_url)
    # Validate the URL
    if not parsed_url.netloc or not parsed_url.path:
        print("Invalid URL provided")
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Invalid URL"})
        }

    s3_key = unquote(parsed_url.path.lstrip('/'))
    bucket_name = 'floorplan-detector'
    s3_client = boto3.client('s3')

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        try:
            s3_client.download_file(bucket_name, s3_key, temp_file.name)
        except Exception as e:
            print(f"Error downloading from S3: {e}")
            return {
                "statusCode": 500,
                "body": json.dumps({"message": "Error downloading file from S3"})
            }

        input_image_path = temp_file.name
        save_image_path = os.path.join("/tmp", f"detected_{os.path.basename(s3_key)}")
        base_name = os.path.basename(s3_key)  # Extracts 'image.png'
        file_name, file_ext = os.path.splitext(base_name)
        modified_name = f"{file_name}_detected{file_ext}"
        save_image_key = os.path.join("dataset_output", modified_name)
        # save_image_key = os.path.join("dataset_output", f"{os.path.basename(s3_key)}_detected")

        # Process the image and get the response
        lambda_client = boto3.client("lambda")
        try:
                response = detect_floorplan_image(input_image_path, save_image_path, lambda_client)
                # Assuming response here is already in the API Gateway expected format
                # Upload the processed image back to S3
                s3_client.upload_file(save_image_path, bucket_name, save_image_key)
                
                # Log the visualizer link for debugging purposes
                # Assuming the 'response' variable is a dictionary that directly contains the 'body' as a serialized JSON string
                response_body = json.loads(response.get('body', '{}'))  # Parsing the 'body' to access the 'paths'
                print(f"visualizer_link:{response_body.get('paths', 'link error')}")

                return response  # Directly return the response from call_visualizer

        except Exception as e:
            print(f"Error in processing: {e}")
            # Return error response
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': str(e)})
            }
        finally:
            # Cleanup temporary file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)


