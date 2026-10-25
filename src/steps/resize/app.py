import json
import boto3
import io
from PIL import Image

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    print(f"Resizing image: {key}")
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        image = Image.open(io.BytesIO(image_data))
        
        max_size = (800, 800)
        image.thumbnail(max_size)
        
        buffer = io.BytesIO()
        image_format = image.format if image.format else 'JPEG'
        image.save(buffer, format=image_format)
        buffer.seek(0)
        
        resized_key = f"resized/{key}"
        s3.put_object(
            Bucket=bucket, 
            Key=resized_key, 
            Body=buffer, 
            ContentType=response['ContentType']
        )
        
        print(f"Successfully resized and saved to {resized_key}")
        
        return {
            "bucket": bucket,
            "key": resized_key,
            "original_key": event['original_key']
        }
    except Exception as e:
        print(f"Resize failed: {str(e)}")
        raise e
