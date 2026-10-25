import json
import boto3
import os
import uuid

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
ORIGIN = os.environ.get('FRONTEND_ORIGIN', '*')

ALLOWED_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png"
}

def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Content-Type": "application/json"
    }
    
    try:
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event.get('body', {})
        file_extension = body.get('file_extension', '.jpg').lower()
        
        if file_extension not in ALLOWED_TYPES:
            return {
                "statusCode": 400, 
                "headers": headers,
                "body": json.dumps({"error": "Invalid file extension. Only .jpg, .jpeg, and .png are allowed."})
            }

        content_type = ALLOWED_TYPES[file_extension]
        object_key = f"uploads/{uuid.uuid4()}{file_extension}"

        presigned_post = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=object_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, 10485760]
            ],
            ExpiresIn=300
        )

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(presigned_post)
        }
    except Exception as e:
        print(f"Error generating URL: {str(e)}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Could not generate upload URL"})
        }
