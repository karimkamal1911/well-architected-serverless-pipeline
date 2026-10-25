import json
import boto3
import io
from PIL import Image

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    print(f"Validating object: {key} in bucket: {bucket}")
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        if len(image_data) > 10 * 1024 * 1024:
            raise ValueError("File size exceeds 10MB limit")
            
        try:
            image = Image.open(io.BytesIO(image_data))
            image.verify()
        except Exception:
            raise ValueError(f"File {key} is corrupt or not a valid image")
            
        print("Validation passed.")
        return event
        
    except Exception as e:
        print(f"Validation failed: {str(e)}")
        raise e
