import json
import os
import boto3

# Initialize the Step Functions client
sfn_client = boto3.client('stepfunctions')

# The ARN of the state machine will be passed via Environment Variable
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    """
    Reads messages from the SQS queue and starts an AWS Step Functions execution.
    """
    print(f"Received {len(event['Records'])} message(s) from SQS.")
    
    for record in event['Records']:
        try:
            # 1. Parse the S3 event payload from the SQS message body
            message_body = json.loads(record['body'])
            
            # 2. Start the Step Functions execution
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps(message_body) # Pass the S3 event to Step Functions
            )
            
            print(f"Successfully started SFN execution: {response['executionArn']}")
            
            # Note: When this Lambda finishes successfully, the SQS message 
            # is automatically deleted by the Event Source Mapping. No manual delete needed!
            
        except Exception as e:
            print(f"Error starting execution: {e}")
            # Raising the exception tells SQS to retry the message or send it to the DLQ
            raise e
            
    return {
        "statusCode": 200,
        "body": json.dumps("Poller execution complete")
    }
