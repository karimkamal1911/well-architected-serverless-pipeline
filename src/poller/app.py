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
    region = os.environ.get('AWS_REGION')
    account = os.environ.get('AWS_ACCOUNT_ID')

    for record in event['Records']:
        message_id = record['messageId']
        try:
            body = json.loads(record['body'])
            for s3_record in body.get('Records', []):
                bucket = s3_record['s3']['bucket']['name']
                key = urllib.parse.unquote_plus(s3_record['s3']['object']['key'])
                eTag = s3_record['s3']['object'].get('eTag', '')
                sequencer = s3_record['s3']['object'].get('sequencer', '')
                
                normalized_payload = {
                    "bucket": bucket,
                    "key": key,
                    "original_key": key
                }
                
                unique_string = f"{bucket}-{key}-{sequencer or eTag}"
                execution_name = hashlib.md5(unique_string.encode()).hexdigest()
                base_execution_arn = f"arn:aws:states:{region}:{account}:execution:{state_machine_name}:{execution_name}"
                
                try:
                    table.put_item(
                        Item={
                            'ImageId': execution_name, 
                            'Status': 'PROCESSING',
                            'ExecutionArn': base_execution_arn
                        },
                        ConditionExpression='attribute_not_exists(ImageId)'
                    )
                    
                    try:
                        sfn_client.start_execution(
                            stateMachineArn=STATE_MACHINE_ARN,
                            name=execution_name, 
                            input=json.dumps(normalized_payload)
                        )
                        print(f"Started SFN execution {execution_name}")
                    except Exception as start_err:
                        print(f"Failed to start execution {execution_name}: {start_err}")
                        try:
                            table.delete_item(
                                Key={'ImageId': execution_name},
                                ConditionExpression="ExecutionArn = :arn",
                                ExpressionAttributeValues={':arn': base_execution_arn}
                            )
                        except Exception as del_err:
                            print(f"Lock deletion failed or lock was updated: {del_err}")
                        raise start_err
                        
                except ClientError as ce:
                    if ce.response['Error']['Code'] == 'ConditionalCheckFailedException':
                        item = table.get_item(Key={'ImageId': execution_name}).get('Item')
                        if not item:
                            continue
                        
                        current_arn = item.get('ExecutionArn', base_execution_arn)
                        
                        try:
                            exec_details = sfn_client.describe_execution(executionArn=current_arn)
                            exec_status = exec_details['status']
                            
                            if exec_status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                                retry_name = f"{execution_name}-retry-{hashlib.md5(os.urandom(16)).hexdigest()[:8]}"
                                retry_arn = f"arn:aws:states:{region}:{account}:execution:{state_machine_name}:{retry_name}"
                                
                                try:
                                    table.update_item(
                                        Key={'ImageId': execution_name},
                                        UpdateExpression="SET #s = :retry_status, ExecutionArn = :new_arn",
                                        ConditionExpression="ExecutionArn = :current_arn",
                                        ExpressionAttributeNames={'#s': 'Status'},
                                        ExpressionAttributeValues={
                                            ':retry_status': 'RETRYING',
                                            ':new_arn': retry_arn,
                                            ':current_arn': current_arn
                                        }
                                    )
                                except ClientError as lock_err:
                                    if lock_err.response['Error']['Code'] == 'ConditionalCheckFailedException':
                                        print("Concurrent retry already claimed. Skipping.")
                                        continue
                                    raise lock_err
                                    
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
                                        UpdateExpression="SET #s = :failed_status",
                                        ConditionExpression="ExecutionArn = :new_arn",
                                        ExpressionAttributeNames={'#s': 'Status'},
                                        ExpressionAttributeValues={
                                            ':failed_status': 'FAILED',
                                            ':new_arn': retry_arn
                                        }
                                    )
                                    raise start_err
                            else:
                                print(f"Execution {current_arn} is {exec_status}. Skipping.")
                        except sfn_client.exceptions.ExecutionDoesNotExist:
                            print(f"Execution missing for lock {execution_name}. Cleaning up.")
                            try:
                                table.delete_item(
                                    Key={'ImageId': execution_name},
                                    ConditionExpression="ExecutionArn = :arn",
                                    ExpressionAttributeValues={':arn': current_arn}
                                )
                            except ClientError as del_err:
                                if del_err.response['Error']['Code'] == 'ConditionalCheckFailedException':
                                    print("Lock was updated by another process. Skipping deletion.")
                                    continue
                                raise del_err
                            raise Exception("Stale lock deleted")
                    else:
                        raise ce
                        
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {"batchItemFailures": batch_item_failures}
