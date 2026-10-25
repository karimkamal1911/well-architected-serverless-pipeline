import json
import os
import boto3
import urllib.parse
import hashlib

sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    batch_item_failures = []

    for record in event['Records']:
        message_id = record['messageId']
        try:
            body = json.loads(record['body'])
            
            for s3_record in body.get('Records', []):
                bucket = s3_record['s3']['bucket']['name']
                key = urllib.parse.unquote_plus(s3_record['s3']['object']['key'])
                eTag = s3_record['s3']['object'].get('eTag', '')
                
                normalized_payload = {
                    "bucket": bucket,
                    "key": key,
                    "original_key": key
                }
                
                unique_string = f"{bucket}-{key}-{eTag}"
                execution_name = hashlib.md5(unique_string.encode()).hexdigest()
                
                sfn_client.start_execution(
                    stateMachineArn=STATE_MACHINE_ARN,
                    name=execution_name, 
                    input=json.dumps(normalized_payload)
                )
                print(f"Successfully started SFN execution {execution_name}")
                
        except sfn_client.exceptions.ExecutionAlreadyExists:
            print(f"Execution for {unique_string} already exists. Skipping duplicate.")
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {"batchItemFailures": batch_item_failures}
