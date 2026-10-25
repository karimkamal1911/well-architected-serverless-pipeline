import json
import boto3
import os

s3 = boto3.client('s3')

def lambda_handler(event, context):
    # The event passed from Step Functions contains our S3 details
    bucket = event['detail']['bucket']['name']
    key = event['detail']['object']['key']
    
    print(f"Validating object: {key} in bucket: {bucket}")
    
    try:
        # Get the object metadata
        response = s3.head_object(Bucket=bucket, Key=key)
        content_type = response.get('ContentType', '')
        
        if 'image' not in content_type:
            raise ValueError(f"File {key} is not a valid image. Type: {content_type}")
            
        print("Validation passed.")
        
        # Pass the data to the next step (Resize)
        return {
            "bucket": bucket,
            "key": key,
            "content_type": content_type
        }
    except Exception as e:
        print(f"Validation failed: {str(e)}")
        raise e
