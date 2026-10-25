import json
import boto3
import io
from PIL import Image, ImageDraw, ImageFont

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    print(f"Watermarking image: {key}")
    
    try:
        # 1. Download resized image
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        # 2. Open image and prepare for watermarking (convert to RGBA for transparency)
        image = Image.open(io.BytesIO(image_data)).convert("RGBA")
        
        # 3. Create a transparent layer for the watermark
        txt = Image.new('RGBA', image.size, (255,255,255,0))
        draw = ImageDraw.Draw(txt)
        
        # 4. Draw text in the bottom left corner (you can adjust this)
        # Using default font for simplicity, but you can load a custom .ttf font
        draw.text((10, image.height - 30), "AWS Pipeline", fill=(255, 255, 255, 128))
        
        # 5. Combine the original image with the watermark layer
        watermarked = Image.alpha_composite(image, txt).convert("RGB")
        
        # 6. Save to in-memory buffer
        buffer = io.BytesIO()
        watermarked.save(buffer, format='JPEG')
        buffer.seek(0)
        
        # 7. Upload watermarked image back to S3
        watermarked_key = f"watermarked/{key}"
        s3.put_object(
            Bucket=bucket, 
            Key=watermarked_key, 
            Body=buffer, 
            ContentType='image/jpeg'
        )
        
        print(f"Successfully watermarked and saved to {watermarked_key}")
        
        # Pass data to the next step (Extract Metadata)
        return {
            "bucket": bucket,
            "key": watermarked_key,
            "original_key": event.get('original_key', key)
        }
    except Exception as e:
        print(f"Watermark failed: {str(e)}")
        raise e
