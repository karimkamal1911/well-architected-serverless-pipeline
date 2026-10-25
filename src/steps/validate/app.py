import json
import boto3
import io
import datetime
from PIL import Image

s3 = boto3.client('s3')
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_FORMATS = ['JPEG', 'PNG']
Image.MAX_IMAGE_PIXELS = 50000000

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    version_id = event.get('versionId')
    
    try:
        params = {'Bucket': bucket, 'Key': key}
        if version_id and version_id != 'null':
            params['VersionId'] = version_id
            
        head_response = s3.head_object(**params)
        content_length = head_response.get('ContentLength', 0)
        last_modified = head_response.get('LastModified')
        
        if not last_modified:
            raise ValueError("Missing LastModified timestamp from S3")
            
        event['upload_time'] = last_modified.astimezone(datetime.timezone.utc).isoformat()
        
        if content_length > MAX_FILE_SIZE:
            raise ValueError(f"File size {content_length} exceeds limit")
        if content_length == 0:
            raise ValueError("File is empty")

        response = s3.get_object(**params)
        image_data = response['Body'].read()
        
        try:
            image = Image.open(io.BytesIO(image_data))
            if image.format not in ALLOWED_FORMATS:
                raise ValueError(f"Format {image.format} not allowed")
            if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions too large")
            image.verify()
        except Image.DecompressionBombError:
            raise ValueError("Decompression bomb detected")
        except Exception as e:
            raise ValueError(f"Corrupt image: {str(e)}")
            
        return event
    except Exception as e:
        print(f"Validation failed: {str(e)}")
        raise e
