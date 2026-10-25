import unittest
from unittest.mock import patch, MagicMock
import os
import io
import time
import json
import datetime
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
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_s3.head_object.return_value = {'ContentLength': 1024, 'LastModified': now}
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'v123'}
        response = validate_handler(event, {})
        self.assertEqual(response['upload_time'], now.isoformat())

    @patch('src.steps.resize.app.s3')
    def test_resize_success(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image()), 'ContentType': 'image/jpeg'}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'v123', 'original_key': 'orig.jpg', 'processing_id': 'abc123', 'attempt_id': 'att1', 'upload_time': '2023-01-01T00:00:00Z'}
        response = resize_handler(event, {})
        self.assertEqual(response['key'], 'resized/abc123/test.jpg')
        self.assertEqual(response['upload_time'], '2023-01-01T00:00:00Z')

    @patch('src.steps.watermark.app.s3')
    def test_watermark_success(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'v123', 'original_key': 'orig.jpg', 'processing_id': 'abc123', 'attempt_id': 'att1', 'upload_time': '2023-01-01T00:00:00Z'}
        response = watermark_handler(event, {})
        self.assertEqual(response['upload_time'], '2023-01-01T00:00:00Z')

    @patch('src.steps.extract_metadata.app.s3')
    def test_metadata_success(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'v123', 'original_key': 'orig.jpg', 'processing_id': 'abc123', 'attempt_id': 'att1', 'upload_time': '2023-01-01T00:00:00Z'}
        response = metadata_handler(event, {})
        self.assertEqual(response['upload_time'], '2023-01-01T00:00:00Z')

    @patch('src.steps.store.app.s3')
    @patch('src.steps.store.app.table')
    @patch('src.steps.store.app.lock_table')
    def test_store_success(self, mock_lock, mock_table, mock_s3):
        event = {
            'bucket': 'test', 'key': 'test.jpg', 'original_key': 'orig.jpg', 'processing_id': 'abc123', 'attempt_id': 'att1',
            'upload_time': '2023-01-01T00:00:00Z',
            'metadata': {'width': 10, 'height': 10, 'format': 'JPEG'}
        }
        response = store_handler(event, {})
        self.assertEqual(response['final_key'], 'processed/abc123/orig.jpg')
        mock_table.put_item.assert_called_once()
        
        # Verify UploadTime is written to DynamoDB
        saved_item = mock_table.put_item.call_args[1]['Item']
        self.assertEqual(saved_item['UploadTime'], '2023-01-01T00:00:00Z')
        self.assertIn('Timestamp', saved_item)

    def test_statemachine_definition(self):
        with open('statemachine/definition.asl.json', 'r') as f:
            asl = json.load(f)
            
        # Check Store transitions to PublishSuccessMessage and has ResultPath
        store_state = asl['States']['Store']
        self.assertEqual(store_state['ResultPath'], '$.storeResult')
        self.assertEqual(store_state['Next'], 'PublishSuccessMessage')
        
        # Check PublishSuccessMessage exists, uses SNS, and stringifies
        success_state = asl['States']['PublishSuccessMessage']
        self.assertEqual(success_state['Parameters']['Message.$'], 'States.JsonToString($)')
        self.assertEqual(success_state['Next'], 'Succeed')
        
        # Check Succeed exists
        self.assertEqual(asl['States']['Succeed']['Type'], 'Succeed')
        
        # Check Failure message also stringifies
        failure_state = asl['States']['PublishFailureMessage']
        self.assertEqual(failure_state['Parameters']['Message.$'], 'States.JsonToString($)')

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

if __name__ == '__main__':
    unittest.main()
