import json
import boto3
import uuid
import os

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('INGEST_BUCKET')

def lambda_handler(event, context):
    try:
        image_id = str(uuid.uuid4())
        file_name = f"{image_id}.jpg"
        
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': BUCKET_NAME, 'Key': file_name},
            ExpiresIn=300
        )
        
        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "upload_url": presigned_url,
                "image_id": image_id
            })
        }
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
