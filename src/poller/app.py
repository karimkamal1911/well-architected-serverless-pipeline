import json
import os
import boto3
import urllib.parse
import hashlib
from botocore.exceptions import ClientError

sfn_client = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')
TABLE_NAME = os.environ.get('TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)

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
                    table.put_item(
                        Item={'ImageId': execution_name, 'Status': 'PROCESSING'},
                        ConditionExpression='attribute_not_exists(ImageId)'
                    )
                except ClientError as ce:
                    if ce.response['Error']['Code'] == 'ConditionalCheckFailedException':
                        execution_arn = f"arn:aws:states:{os.environ.get('AWS_REGION')}:{os.environ.get('AWS_ACCOUNT_ID')}:execution:{state_machine_name}:{execution_name}"
                        exec_details = sfn_client.describe_execution(executionArn=execution_arn)
                        status = exec_details['status']
                        
                        if status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                            try:
                                table.update_item(
                                    Key={'ImageId': execution_name},
                                    UpdateExpression="SET #s = :new_status",
                                    ConditionExpression="#s IN (:fail, :timeout, :abort)",
                                    ExpressionAttributeNames={'#s': 'Status'},
                                    ExpressionAttributeValues={
                                        ':new_status': 'RETRYING',
                                        ':fail': 'FAILED',
                                        ':timeout': 'TIMED_OUT',
                                        ':abort': 'ABORTED'
                                    }
                                )
                            except ClientError as lock_err:
                                if lock_err.response['Error']['Code'] == 'ConditionalCheckFailedException':
                                    print("Concurrent retry already claimed. Skipping.")
                                    continue
                                raise lock_err
                                
                            retry_name = f"{execution_name}-retry-{hashlib.md5(os.urandom(16)).hexdigest()[:8]}"
                            try:
                                sfn_client.start_execution(
                                    stateMachineArn=STATE_MACHINE_ARN,
                                    name=retry_name,
                                    input=json.dumps(normalized_payload)
                                )
                                print(f"Retried failed execution as {retry_name}")
                            except Exception as start_err:
                                table.update_item(
                                    Key={'ImageId': execution_name},
                                    UpdateExpression="SET #s = :fail",
                                    ExpressionAttributeNames={'#s': 'Status'},
                                    ExpressionAttributeValues={':fail': 'FAILED'}
                                )
                                raise start_err
                        else:
                            print(f"Execution {execution_name} is {status}. Skipping.")
                        continue
                    else:
                        raise ce
                
                try:
                    sfn_client.start_execution(
                        stateMachineArn=STATE_MACHINE_ARN,
                        name=execution_name, 
                        input=json.dumps(normalized_payload)
                    )
                    print(f"Started SFN execution {execution_name}")
                except Exception as start_err:
                    print(f"Failed to start execution {execution_name}: {start_err}")
                    table.delete_item(Key={'ImageId': execution_name})
                    raise start_err
                        
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {"batchItemFailures": batch_item_failures}
