import unittest
from unittest.mock import patch, MagicMock
import os
import io
import time
import json
from PIL import Image
from botocore.exceptions import ClientError

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_EC2_METADATA_DISABLED'] = 'true'
os.environ['BUCKET_NAME'] = 'test-bucket'
os.environ['DEST_BUCKET'] = 'dest-bucket'
os.environ['TABLE_NAME'] = 'test-table'
os.environ['LOCK_TABLE_NAME'] = 'lock-table'
os.environ['STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:Test'

from src.steps.validate.app import lambda_handler as validate_handler
from src.steps.resize.app import lambda_handler as resize_handler
from src.steps.watermark.app import lambda_handler as watermark_handler
from src.steps.extract_metadata.app import lambda_handler as metadata_handler
from src.steps.store.app import lambda_handler as store_handler
from src.poller.app import lambda_handler as poller_handler

class TestPipeline(unittest.TestCase):

    def create_dummy_image(self):
        img = Image.new('RGB', (10, 10), color = 'red')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        return buf.read()

    @patch('src.steps.validate.app.s3')
    def test_validate_success(self, mock_s3):
        mock_s3.head_object.return_value = {'ContentLength': 1024}
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'v123'}
        response = validate_handler(event, {})
        self.assertEqual(response['versionId'], 'v123')

    @patch('src.steps.resize.app.s3')
    def test_resize_success(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image()), 'ContentType': 'image/jpeg'}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'v123', 'original_key': 'orig.jpg', 'processing_id': 'abc123', 'attempt_id': 'att1'}
        response = resize_handler(event, {})
        self.assertEqual(response['key'], 'resized/abc123/test.jpg')

    @patch('src.steps.store.app.s3')
    @patch('src.steps.store.app.table')
    @patch('src.steps.store.app.lock_table')
    def test_store_success(self, mock_lock, mock_table, mock_s3):
        event = {
            'bucket': 'test', 'key': 'test.jpg', 'original_key': 'orig.jpg', 'processing_id': 'abc123', 'attempt_id': 'att1',
            'metadata': {'width': 10, 'height': 10, 'format': 'JPEG'}
        }
        response = store_handler(event, {})
        mock_lock.update_item.assert_called_once()
        self.assertEqual(mock_lock.update_item.call_args[1]['ExpressionAttributeValues'][':a'], 'att1')

    @patch('src.poller.app.sfn')
    @patch('src.poller.app.lock_table')
    @patch('time.time')
    def test_poller_start_timeout_does_not_delete_lock(self, mock_time, mock_table, mock_sfn):
        mock_time.return_value = 1000
        mock_table.put_item.return_value = {}
        mock_sfn.start_execution.side_effect = Exception("Timeout")
        
        event = {
            'Records': [{
                'messageId': '123',
                'body': '{"Records":[{"s3":{"bucket":{"name":"test"},"object":{"key":"test.jpg","versionId":"v1"}}}]}'
            }]
        }
        response = poller_handler(event, {})
        self.assertEqual(len(response['batchItemFailures']), 1)
        mock_table.delete_item.assert_not_called()

    @patch('src.poller.app.sfn')
    @patch('src.poller.app.lock_table')
    @patch('time.time')
    def test_poller_stale_execution_is_running(self, mock_time, mock_table, mock_sfn):
        mock_time.return_value = 1000
        mock_table.put_item.side_effect = ClientError({'Error': {'Code': 'ConditionalCheckFailedException'}}, 'PutItem')
        mock_table.get_item.return_value = {'Item': {'Status': 'PROCESSING', 'LeaseExpiry': 500, 'ExecutionArn': 'proc-abc-att1'}}
        
        mock_sfn.describe_execution.return_value = {'status': 'RUNNING'}
        mock_sfn.exceptions.ExecutionDoesNotExist = ClientError
        
        event = {
            'Records': [{
                'messageId': '123',
                'body': '{"Records":[{"s3":{"bucket":{"name":"test"},"object":{"key":"test.jpg","versionId":"v1"}}}]}'
            }]
        }
        response = poller_handler(event, {})
        self.assertEqual(len(response['batchItemFailures']), 0)
        mock_table.update_item.assert_called_once()
        mock_sfn.start_execution.assert_not_called()

    @patch('src.poller.app.sfn')
    @patch('src.poller.app.lock_table')
    @patch('time.time')
    def test_poller_missing_version(self, mock_time, mock_table, mock_sfn):
        mock_time.return_value = 1000
        event = {
            'Records': [{
                'messageId': '123',
                'body': '{"Records":[{"s3":{"bucket":{"name":"test"},"object":{"key":"test.jpg"}}}]}'
            }]
        }
        response = poller_handler(event, {})
        self.assertEqual(len(response['batchItemFailures']), 1)
        mock_sfn.start_execution.assert_not_called()

if __name__ == '__main__':
    unittest.main()
