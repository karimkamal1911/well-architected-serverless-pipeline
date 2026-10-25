import json
import boto3
import os
from PIL import Image
import io

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    print(f"Resizing image: {key}")
    
    try:
        # 1. Download image from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        # 2. Open with Pillow and resize
        image = Image.open(io.BytesIO(image_data))
        
        # Resize keeping aspect ratio (max width/height 800px)
        max_size = (800, 800)
        image.thumbnail(max_size)
        
        # 3. Save resized image to an in-memory buffer
        buffer = io.BytesIO()
        image_format = image.format if image.format else 'JPEG'
        image.save(buffer, format=image_format)
        buffer.seek(0)
        
        # 4. Upload resized image back to S3 (temp location)
        resized_key = f"resized/{key}"
        s3.put_object(
            Bucket=bucket, 
            Key=resized_key, 
            Body=buffer, 
            ContentType=response['ContentType']
        )
        
        print(f"Successfully resized and saved to {resized_key}")
        
        # Pass data to the next step (Watermark)
        return {
            "bucket": bucket,
            "key": resized_key,
            "original_key": event.get('original_key', key)
        }
    except Exception as e:
        print(f"Resize failed: {str(e)}")
        # Raising the exception tells Step Functions to catch the error and retry/fail
        raise e
