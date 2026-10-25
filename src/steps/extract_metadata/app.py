import json
import boto3
import io
from PIL import Image

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        image = Image.open(io.BytesIO(image_data))
        
        metadata = {
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "size_bytes": len(image_data)
        }
        
        return {
            "bucket": bucket,
            "key": key,
            "original_key": event['original_key'],
            "versionId": event['versionId'],
            "processing_id": event['processing_id'],
            "attempt_id": event['attempt_id'],
            "upload_time": event['upload_time'],
            "metadata": metadata
        }
    except Exception as e:
        print(f"Metadata extraction failed: {str(e)}")
        raise e
