import json
import boto3
import os
import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

DEST_BUCKET = os.environ.get('DEST_BUCKET')
TABLE_NAME = os.environ.get('TABLE_NAME')
LOCK_TABLE_NAME = os.environ.get('LOCK_TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)
lock_table = dynamodb.Table(LOCK_TABLE_NAME)

def lambda_handler(event, context):
    source_bucket = event['bucket']
    source_key = event['key']
    original_key = event['original_key']
    processing_id = event['processing_id']
    attempt_id = event['attempt_id']
    upload_time = event['upload_time']
    metadata = event['metadata']
    
    try:
        base_key = os.path.splitext(os.path.basename(original_key))[0]
        final_key = f"processed/{processing_id}/{base_key}.jpg"
        copy_source = {'Bucket': source_bucket, 'Key': source_key}
        
        s3.copy_object(
            CopySource=copy_source,
            Bucket=DEST_BUCKET,
            Key=final_key,
            ContentType='image/jpeg',
            MetadataDirective='REPLACE'
        )
        
        table.put_item(
            Item={
                'ProcessingId': processing_id,
                'OriginalKey': original_key,
                'UploadTime': upload_time,
                'Timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'Status': 'COMPLETED',
                'Width': metadata.get('width'),
                'Height': metadata.get('height'),
                'Format': metadata.get('format'),
                'DestinationKey': final_key
            }
        )
        
        lock_table.update_item(
            Key={'ProcessingId': processing_id},
            UpdateExpression="SET #s = :s",
            ConditionExpression="AttemptId = :a",
            ExpressionAttributeNames={'#s': 'Status'},
            ExpressionAttributeValues={':s': 'SUCCEEDED', ':a': attempt_id}
        )
        
        return {
            "statusCode": 200,
            "message": "Image stored successfully",
            "final_key": final_key,
            "processing_id": processing_id,
            "original_key": original_key,
            "upload_time": upload_time
        }
    except Exception as e:
        print(f"Store step failed: {str(e)}")
        raise e
