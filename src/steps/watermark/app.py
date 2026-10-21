import json
import boto3
from PIL import Image

def lambda_handler(event, context):
    """
    Step 3: Add a watermark to the resized image.
    """
    print(f"Watermarking image based on event: {json.dumps(event)}")
    # TODO: Apply watermark logic
    
    return {
        "statusCode": 200,
        "message": "Watermark applied successfully"
    }
