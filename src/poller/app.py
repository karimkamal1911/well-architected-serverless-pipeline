import json
import os
import boto3
import urllib.parse

sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    # We need to return a list of failed message IDs for partial batch failure handling
    batch_item_failures = []

    for record in event['Records']:
        message_id = record['messageId']
        try:
            # Parse the SQS message body which contains the S3 event
            body = json.loads(record['body'])
            
            # Handle standard S3 event records (S3 can batch multiple records)
            for s3_record in body.get('Records', []):
                bucket = s3_record['s3']['bucket']['name']
                
                # S3 keys are URL-encoded (e.g., spaces become %20). We must decode them.
                key = urllib.parse.unquote_plus(s3_record['s3']['object']['key'])
                
                # Normalize the payload for Step Functions so all steps get the same schema
                normalized_payload = {
                    "bucket": bucket,
                    "key": key,
                    "original_key": key
                }
                
                # Start the Step Functions execution
                # We use the SQS message_id as the execution name to prevent duplicate executions
                sfn_client.start_execution(
                    stateMachineArn=STATE_MACHINE_ARN,
                    name=f"process-{message_id}", 
                    input=json.dumps(normalized_payload)
                )
                print(f"Successfully started SFN execution for message {message_id}")
                
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            # Add to failures list so SQS knows to retry ONLY this message
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {"batchItemFailures": batch_item_failures}
