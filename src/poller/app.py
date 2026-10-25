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
    parts = STATE_MACHINE_ARN.split(':')
    region, account, state_machine_name = parts[3], parts[4], parts[6]
    
    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            for s3_rec in body.get('Records', []):
                bucket = s3_rec['s3']['bucket']['name']
                key = urllib.parse.unquote_plus(s3_rec['s3']['object']['key'])
                version_id = s3_rec['s3']['object'].get('versionId')
                
                if not version_id or version_id == 'null':
                    raise ValueError("Missing or null versionId.")
                
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
                    
                    item = lock_table.get_item(Key={'ProcessingId': processing_id}, ConsistentRead=True).get('Item')
                    if not item:
                        raise Exception("Race condition on lock table get_item")
                    
                    status = item.get('Status')
                    item_lease = item.get('LeaseExpiry', 0)
                    current_exec = item.get('ExecutionArn', exec_name)
                    
                    if status == 'SUCCEEDED':
                        continue
                    elif status == 'FAILED':
                        continue
                    elif item_lease > now:
                        print(f"Processing {processing_id} is actively leased. Skipping.")
                        continue
                    
                    try:
                        exec_arn = f"arn:aws:states:{region}:{account}:execution:{state_machine_name}:{current_exec}"
                        exec_details = sfn.describe_execution(executionArn=exec_arn)
                        exec_status = exec_details['status']
                        
                        if exec_status == 'RUNNING':
                            lock_table.update_item(
                                Key={'ProcessingId': processing_id},
                                UpdateExpression="SET LeaseExpiry = :l",
                                ConditionExpression="ExecutionArn = :e",
                                ExpressionAttributeValues={':l': lease, ':e': current_exec}
                            )
                            continue
                        elif exec_status == 'SUCCEEDED':
                            lock_table.update_item(
                                Key={'ProcessingId': processing_id},
                                UpdateExpression="SET #s = :s",
                                ConditionExpression="ExecutionArn = :e",
                                ExpressionAttributeNames={'#s': 'Status'},
                                ExpressionAttributeValues={':s': 'SUCCEEDED', ':e': current_exec}
                            )
                            continue
                    except sfn.exceptions.ExecutionDoesNotExist:
                        pass 
                    
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
                            continue
                        raise claim_err
                
                try:
                    sfn.start_execution(stateMachineArn=STATE_MACHINE_ARN, name=exec_name, input=json.dumps(payload))
                except sfn.exceptions.ExecutionAlreadyExists:
                    pass
                except Exception as start_err:
                    print(f"Ambiguous start error for {exec_name}: {start_err}. Relying on SQS retry to reconcile.")
                    raise start_err
                        
        except Exception as e:
            print(f"Error processing message {record['messageId']}: {str(e)}")
            failures.append({'itemIdentifier': record['messageId']})
            
    return {'batchItemFailures': failures}
