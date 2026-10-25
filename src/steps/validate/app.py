import json
import boto3
import io
from PIL import Image

s3 = boto3.client('s3')

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_FORMATS = ['JPEG', 'PNG']
Image.MAX_IMAGE_PIXELS = 50000000

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
                
            if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError(f"Image pixel count ({image.width * image.height}) exceeds limit of {Image.MAX_IMAGE_PIXELS}")

            image.verify()
        except Image.DecompressionBombError:
            raise ValueError("Decompression bomb detected")
        except Exception as e:
            raise ValueError(f"File {key} is corrupt or not a valid image: {str(e)}")
            
        print("Validation passed.")
        return event
        
    except Exception as e:
        print(f"Validation failed: {str(e)}")
        raise e
