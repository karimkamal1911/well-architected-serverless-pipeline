import json
import boto3
import os

sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    for record in event['Records']:
        body = json.loads(record['body'])
        s3_event = body['Records'][0]['s3']
        bucket = s3_event['bucket']['name']
        key = s3_event['object']['key']
        
        payload = {
            "bucket": bucket,
            "key": key
        }
        
        sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(payload)
        )
        
    return "Successfully processed SQS batch"
