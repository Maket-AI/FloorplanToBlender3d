
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


def local_test():
    print(floorplan_lib_path)

    image_names = ["floorplan_google2.jpg"]
    for image_name in image_names:
        input_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "events/", image_name))
        save_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__),"outputs", f"detected_{image_name}"))
        # Call the processing function
        return detect_floorplan_image(input_image_path, save_image_path, lambda_client)


def lambda_handler(event, context):
    # Extract the URL from the event
    image_url = event['image_url']
    parsed_url = urlparse(image_url)
    # Validate the URL
    if not parsed_url.netloc or not parsed_url.path:
        raise ValueError("Invalid URL in the event")
    # Extract the object key from the URL
    s3_key = unquote(parsed_url.path.lstrip('/'))
    # Known bucket name
    bucket_name = 'floorplan-detector'
    # Initialize S3 client
    s3_client = boto3.client('s3')

    # Create a temporary file to store the downloaded image
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        try:
            # Download the image from S3 to the temp file
            s3_client.download_file(bucket_name, s3_key, temp_file.name)
        except Exception as e:
            print(f"Unable to download the file from S3: {e}")
            return {
                "statusCode": 500,
                "body": json.dumps({"message": "Error downloading file from S3"})
            }

        # Process the downloaded image
        input_image_path = temp_file.name
        save_image_path = os.path.join("/tmp", f"detected_{os.path.basename(s3_key)}")
        lambda_client = boto3.client("lambda")
        response = detect_floorplan_image(input_image_path, save_image_path, lambda_client)
        # (Optionally) Upload the processed image back to S3

    # (Optional) Delete the temporary file
    os.unlink(temp_file.name)

    return response


if __name__ == "__main__":
    event = {
        "image_url": "https://floorplan-detector.s3.ca-central-1.amazonaws.com/2024-01-03/floorplan_google2.jpg"
    }
    response = lambda_handler(event, "")
    print(f"final response:{response['path']}")
