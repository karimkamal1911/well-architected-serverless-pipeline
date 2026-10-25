import json
import boto3

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    print(f"Validating object: {key} in bucket: {bucket}")
    
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        content_type = response.get('ContentType', '')
        
        if 'image' not in content_type:
            raise ValueError(f"File {key} is not a valid image. Type: {content_type}")
            
        print("Validation passed.")
        return event
        
    except Exception as e:
        print(f"Validation failed: {str(e)}")
        raise e
