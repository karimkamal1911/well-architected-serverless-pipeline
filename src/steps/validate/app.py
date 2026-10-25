import json
import boto3
import io
from PIL import Image

s3 = boto3.client('s3')

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_FORMATS = ['JPEG', 'PNG']

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    print(f"Validating object: {key} in bucket: {bucket}")
    
    try:
        head_response = s3.head_object(Bucket=bucket, Key=key)
        content_length = head_response.get('ContentLength', 0)
        
        if content_length > MAX_FILE_SIZE:
            raise ValueError(f"File size {content_length} bytes exceeds 10MB limit")
            
        if content_length == 0:
            raise ValueError("File is empty")

        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        try:
            image = Image.open(io.BytesIO(image_data))
            
            if image.format not in ALLOWED_FORMATS:
                raise ValueError(f"Format {image.format} not allowed. Only JPEG and PNG are supported.")
                
            max_dimension = 10000
            if image.width > max_dimension or image.height > max_dimension:
                raise ValueError(f"Image dimensions {image.width}x{image.height} exceed maximum limit of {max_dimension}px")

            image.verify()
        except Exception as e:
            raise ValueError(f"File {key} is corrupt or not a valid image: {str(e)}")
            
        print("Validation passed.")
        return event
        
    except Exception as e:
        print(f"Validation failed: {str(e)}")
        raise e
