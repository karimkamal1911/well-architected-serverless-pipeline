import json
import boto3
import os
import uuid

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

ALLOWED_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png"
}

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event.get('body', {})
        file_extension = body.get('file_extension', '.jpg').lower()
        
        if file_extension not in ALLOWED_TYPES:
            return {
                "statusCode": 400, 
                "body": json.dumps({"error": "Invalid file extension. Only .jpg, .jpeg, and .png are allowed."})
            }

        content_type = ALLOWED_TYPES[file_extension]
        object_key = f"uploads/{uuid.uuid4()}{file_extension}"

        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key,
                'ContentType': content_type
            },
            ExpiresIn=300
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "upload_url": presigned_url,
                "object_key": object_key
            })
        }
    except Exception as e:
        print(f"Error generating URL: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Could not generate upload URL"})
        }
