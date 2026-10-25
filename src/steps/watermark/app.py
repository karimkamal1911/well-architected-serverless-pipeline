import json
import boto3
import os
import io
from PIL import Image, ImageDraw

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    processing_id = event['processing_id']
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        image = Image.open(io.BytesIO(image_data)).convert("RGBA")
        txt = Image.new('RGBA', image.size, (255,255,255,0))
        draw = ImageDraw.Draw(txt)
        draw.text((10, image.height - 30), "AWS Pipeline", fill=(255, 255, 255, 128))
        
        watermarked = Image.alpha_composite(image, txt).convert("RGB")
        buffer = io.BytesIO()
        watermarked.save(buffer, format='JPEG')
        buffer.seek(0)
        
        base_key = os.path.splitext(os.path.basename(key))[0]
        watermarked_key = f"watermarked/{processing_id}/{base_key}.jpg"
        
        s3.put_object(Bucket=bucket, Key=watermarked_key, Body=buffer, ContentType='image/jpeg')
        
        return {
            "bucket": bucket,
            "key": watermarked_key,
            "original_key": event['original_key'],
            "versionId": event['versionId'],
            "processing_id": processing_id,
            "attempt_id": event['attempt_id'],
            "upload_time": event['upload_time']
        }
    except Exception as e:
        print(f"Watermark failed: {str(e)}")
        raise e
