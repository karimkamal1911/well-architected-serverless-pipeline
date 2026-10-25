import json
import boto3
import os
import io
from PIL import Image

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    version_id = event.get('versionId')
    processing_id = event['processing_id']
    
    try:
        params = {'Bucket': bucket, 'Key': key}
        if version_id and version_id != 'null':
            params['VersionId'] = version_id
            
        response = s3.get_object(**params)
        image_data = response['Body'].read()
        
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail((800, 800))
        
        buffer = io.BytesIO()
        image_format = image.format if image.format else 'JPEG'
        image.save(buffer, format=image_format)
        buffer.seek(0)
        
        resized_key = f"resized/{processing_id}/{os.path.basename(key)}"
        s3.put_object(Bucket=bucket, Key=resized_key, Body=buffer, ContentType=response['ContentType'])
        
        return {
            "bucket": bucket,
            "key": resized_key,
            "original_key": event['original_key'],
            "versionId": version_id,
            "processing_id": processing_id,
            "attempt_id": event['attempt_id'],
            "upload_time": event['upload_time']
        }
    except Exception as e:
        print(f"Resize failed: {str(e)}")
        raise e
