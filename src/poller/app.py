import json
import os
import boto3
import urllib.parse
import hashlib
import time

sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    batch_item_failures = []

    state_machine_name = STATE_MACHINE_ARN.split(':')[-1]

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
                
                try:
                    sfn_client.start_execution(
                        stateMachineArn=STATE_MACHINE_ARN,
                        name=execution_name, 
                        input=json.dumps(normalized_payload)
                    )
                    print(f"Successfully started SFN execution {execution_name}")
                    
                except sfn_client.exceptions.ExecutionAlreadyExists:
                    execution_arn = f"arn:aws:states:{os.environ.get('AWS_REGION')}:{os.environ.get('AWS_ACCOUNT_ID')}:execution:{state_machine_name}:{execution_name}"
                    
                    try:
                        exec_details = sfn_client.describe_execution(executionArn=execution_arn)
                        status = exec_details['status']
                        
                        if status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                            retry_name = f"{execution_name}-retry-{int(time.time())}"
                            sfn_client.start_execution(
                                stateMachineArn=STATE_MACHINE_ARN,
                                name=retry_name,
                                input=json.dumps(normalized_payload)
                            )
                            print(f"Previous execution failed. Started retry execution {retry_name}")
                        else:
                            print(f"Execution {execution_name} is {status}. Skipping duplicate.")
                    except Exception as inner_e:
                        print(f"Error checking execution status: {str(inner_e)}")
                        raise inner_e
                        
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {"batchItemFailures": batch_item_failures}
