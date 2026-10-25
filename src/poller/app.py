import json
import os
import boto3

sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    print(f"Received {len(event['Records'])} messages from SQS.")
    
    # We need to return a list of failed message IDs for partial batch failure handling
    batch_item_failures = []

    for record in event['Records']:
        message_id = record['messageId']
        try:
            # Parse the S3 event payload from the SQS message body
            message_body = json.loads(record['body'])
            
            # Start the Step Functions execution
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps(message_body)
            )
            print(f"Successfully started SFN execution: {response['executionArn']} for message {message_id}")
            
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            # Add to failures list so SQS knows to retry ONLY this message
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {"batchItemFailures": batch_item_failures}
