import json
import boto3
import io
from PIL import Image

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    print(f"Extracting metadata for: {key}")
    
    try:
        # 1. Download the watermarked image
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        # 2. Open with Pillow to read properties
        image = Image.open(io.BytesIO(image_data))
        
        # 3. Extract metadata
        metadata = {
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "size_bytes": len(image_data)
        }
        
        print(f"Extracted metadata: {metadata}")
        
        # 4. Pass data to the final step (Store)
        return {
            "bucket": bucket,
            "key": key,
            "original_key": event.get('original_key', key),
            "metadata": metadata
        }
    except Exception as e:
        print(f"Metadata extraction failed: {str(e)}")
        raise e
