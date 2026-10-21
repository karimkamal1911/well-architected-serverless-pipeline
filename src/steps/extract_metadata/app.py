import json
import boto3

def lambda_handler(event, context):
    """
    Step 4: Extract metadata from the image (dimensions, format, etc.)
    """
    print(f"Extracting metadata based on event: {json.dumps(event)}")
    # TODO: Extract image info
    
    return {
        "statusCode": 200,
        "message": "Metadata extracted successfully"
    }
