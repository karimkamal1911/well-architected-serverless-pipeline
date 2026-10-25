import json
import boto3
import os
from datetime import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# These environment variables are passed in from the SAM template
DEST_BUCKET = os.environ.get('DEST_BUCKET')
TABLE_NAME = os.environ.get('TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    source_bucket = event['bucket']
    source_key = event['key']
    original_key = event['original_key']
    metadata = event['metadata']
    
    print(f"Storing final image and metadata for {original_key}")
    
    try:
        # 1. Copy the processed image from the temp bucket to the final Destination Bucket
        final_key = f"processed/{original_key}"
        copy_source = {'Bucket': source_bucket, 'Key': source_key}
        
        s3.copy_object(
            CopySource=copy_source,
            Bucket=DEST_BUCKET,
            Key=final_key
        )
        
        # 2. Write the metadata to DynamoDB
        table.put_item(
            Item={
                'ImageId': original_key,
                'Timestamp': datetime.utcnow().isoformat(),
                'Status': 'COMPLETED',
                'Width': metadata.get('width'),
                'Height': metadata.get('height'),
                'Format': metadata.get('format'),
                'DestinationKey': final_key
            }
        )
        
        print(f"Successfully stored image at {final_key} and metadata in DynamoDB.")
        
        return {
            "statusCode": 200,
            "message": "Image stored successfully",
            "final_key": final_key
        }
    except Exception as e:
        print(f"Store step failed: {str(e)}")
        raise e
