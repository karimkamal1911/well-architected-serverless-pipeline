import json
import os
import boto3
import urllib.parse
import hashlib
import time
import uuid
from botocore.exceptions import ClientError

sfn = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
lock_table = dynamodb.Table(os.environ['LOCK_TABLE_NAME'])
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

def lambda_handler(event, context):
    failures = []
    state_machine_name = STATE_MACHINE_ARN.split(':')[-1]
    region = os.environ.get('AWS_REGION')
    account = STATE_MACHINE_ARN.split(':')[4]
    
    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            for s3_rec in body.get('Records', []):
                bucket = s3_rec['s3']['bucket']['name']
                key = urllib.parse.unquote_plus(s3_rec['s3']['object']['key'])
                version_id = s3_rec['s3']['object'].get('versionId')
                
                if not version_id or version_id == 'null':
                    raise ValueError("Missing or null versionId. S3 versioning is required.")
                
                payload_str = json.dumps({"bucket": bucket, "key": key, "versionId": version_id}, sort_keys=True)
                processing_id = hashlib.sha256(payload_str.encode()).hexdigest()
                
                attempt_id = uuid.uuid4().hex[:8]
                exec_name = f"proc-{processing_id[:60]}-{attempt_id}"
                
                payload = {
                    "bucket": bucket,
                    "key": key,
                    "original_key": key,
                    "versionId": version_id,
                    "processing_id": processing_id,
                    "attempt_id": attempt_id
                }
                
                now = int(time.time())
                lease = now + 60
                
                try:
                    lock_table.put_item(
                        Item={'ProcessingId': processing_id, 'Status': 'PROCESSING', 'LeaseExpiry': lease, 'ExecutionArn': exec_name, 'AttemptId': attempt_id},
                        ConditionExpression='attribute_not_exists(ProcessingId)'
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                        raise
                    
                    item = lock_table.get_item(Key={'ProcessingId': processing_id}).get('Item')
                    if not item:
                        raise Exception("Race condition on lock table get_item")
                    
                    status = item.get('Status')
                    item_lease = item.get('LeaseExpiry', 0)
                    
                    if status == 'SUCCEEDED':
                        print(f"Processing {processing_id} already SUCCEEDED. Skipping.")
                        continue
                    elif item_lease > now:
                        print(f"Processing {processing_id} is actively leased. Skipping.")
                        continue
                    
                    current_arn = item.get('ExecutionArn', exec_name)
                    try:
                        exec_details = sfn.describe_execution(executionArn=f"arn:aws:states:{region}:{account}:execution:{state_machine_name}:{current_arn}")
                        exec_status = exec_details['status']
                        if exec_status == 'RUNNING':
                            print(f"Execution {current_arn} is RUNNING. Extending lease.")
                            lock_table.update_item(
                                Key={'ProcessingId': processing_id},
                                UpdateExpression="SET LeaseExpiry = :l",
                                ExpressionAttributeValues={':l': lease}
                            )
                            continue
                        elif exec_status == 'SUCCEEDED':
                            lock_table.update_item(
                                Key={'ProcessingId': processing_id},
                                UpdateExpression="SET #s = :s",
                                ExpressionAttributeNames={'#s': 'Status'},
                                ExpressionAttributeValues={':s': 'SUCCEEDED'}
                            )
                            continue
                        elif exec_status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                            print(f"Execution {current_arn} failed. Preparing retry.")
                    except sfn.exceptions.ExecutionDoesNotExist:
                        print(f"Execution {current_arn} missing. Safe to claim.")
                    
                    try:
                        lock_table.update_item(
                            Key={'ProcessingId': processing_id},
                            UpdateExpression="SET #s = :s, LeaseExpiry = :l, ExecutionArn = :e, AttemptId = :a",
                            ConditionExpression="LeaseExpiry = :old_l",
                            ExpressionAttributeNames={'#s': 'Status'},
                            ExpressionAttributeValues={
                                ':s': 'PROCESSING',
                                ':l': lease,
                                ':e': exec_name,
                                ':a': attempt_id,
                                ':old_l': item_lease
                            }
                        )
                    except ClientError as claim_err:
                        if claim_err.response['Error']['Code'] == 'ConditionalCheckFailedException':
                            print("Concurrent retry claimed by another invocation. Skipping.")
                            continue
                        raise claim_err
                
                try:
                    sfn.start_execution(
                        stateMachineArn=STATE_MACHINE_ARN,
                        name=exec_name,
                        input=json.dumps(payload)
                    )
                    print(f"Started SFN execution {exec_name}")
                except sfn.exceptions.ExecutionAlreadyExists:
                    print(f"Execution {exec_name} already exists. Checking status.")
                except Exception as start_err:
                    print(f"Failed to start execution {exec_name}: {start_err}")
                    try:
                        lock_table.delete_item(
                            Key={'ProcessingId': processing_id},
                            ConditionExpression="ExecutionArn = :e AND AttemptId = :a",
                            ExpressionAttributeValues={':e': exec_name, ':a': attempt_id}
                        )
                    except Exception as del_err:
                        print(f"Conditional deletion failed: {del_err}")
                    raise start_err
                        
        except Exception as e:
            print(f"Error processing message {record['messageId']}: {str(e)}")
            failures.append({'itemIdentifier': record['messageId']})
            
    return {'batchItemFailures': failures}
