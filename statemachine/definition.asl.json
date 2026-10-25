{
  "Comment": "Serverless Image Processing Workflow",
  "StartAt": "Validate",
  "States": {
    "Validate": {
      "Type": "Task",
      "Resource": "${ValidateFunctionArn}",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "States.Timeout"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "MarkFailed"
        }
      ],
      "Next": "Resize"
    },
    "Resize": {
      "Type": "Task",
      "Resource": "${ResizeFunctionArn}",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "States.Timeout"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "MarkFailed"
        }
      ],
      "Next": "Watermark"
    },
    "Watermark": {
      "Type": "Task",
      "Resource": "${WatermarkFunctionArn}",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "States.Timeout"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "MarkFailed"
        }
      ],
      "Next": "ExtractMetadata"
    },
    "ExtractMetadata": {
      "Type": "Task",
      "Resource": "${ExtractMetadataFunctionArn}",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "States.Timeout"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "MarkFailed"
        }
      ],
      "Next": "Store"
    },
    "Store": {
      "Type": "Task",
      "Resource": "${StoreFunctionArn}",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "States.Timeout"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "MarkFailed"
        }
      ],
      "ResultPath": "$.storeResult",
      "Next": "PublishSuccessMessage"
    },
    "PublishSuccessMessage": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotificationTopicArn}",
        "Message.$": "States.JsonToString($)"
      },
      "Next": "Succeed"
    },
    "Succeed": {
      "Type": "Succeed"
    },
    "MarkFailed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName": "${LockTableName}",
        "Key": {
          "ProcessingId": {"S.$": "$.processing_id"}
        },
        "UpdateExpression": "SET #s = :s",
        "ConditionExpression": "AttemptId = :a",
        "ExpressionAttributeNames": {"#s": "Status"},
        "ExpressionAttributeValues": {
          ":s": {"S": "FAILED"},
          ":a": {"S.$": "$.attempt_id"}
        }
      },
      "ResultPath": null,
      "Next": "PublishFailureMessage",
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.markFailedError",
          "Next": "PublishFailureMessage"
        }
      ]
    },
    "PublishFailureMessage": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotificationTopicArn}",
        "Message.$": "States.JsonToString($)"
      },
      "Next": "ProcessingFailed"
    },
    "ProcessingFailed": {
      "Type": "Fail",
      "Error": "ProcessingFailed",
      "Cause": "The image processing workflow failed."
    }
  }
}
