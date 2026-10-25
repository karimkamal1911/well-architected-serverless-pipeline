import json
import boto3
import os
import uuid

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def lambda_handler(event, context):
    try:
        # Generate a unique filename to prevent overwriting
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event.get('body', {})
        file_extension = body.get('file_extension', '.jpg')
        object_key = f"uploads/{uuid.uuid4()}{file_extension}"

        # Generate the presigned URL (valid for 5 minutes)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key,
                'ContentType': 'image/jpeg' # Can be parameterized later
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
