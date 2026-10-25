import unittest
from unittest.mock import patch, MagicMock
import os
import io
import time
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
    def test_validate_success_version(self, mock_s3):
        mock_s3.head_object.return_value = {'ContentLength': 1024}
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'v123'}
        response = validate_handler(event, {})
        mock_s3.head_object.assert_called_with(Bucket='test', Key='test.jpg', VersionId='v123')
        self.assertEqual(response['versionId'], 'v123')

    @patch('src.steps.validate.app.s3')
    def test_validate_missing_version(self, mock_s3):
        mock_s3.head_object.return_value = {'ContentLength': 1024}
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'versionId': 'null'}
        response = validate_handler(event, {})
        mock_s3.head_object.assert_called_with(Bucket='test', Key='test.jpg')

    @patch('src.steps.resize.app.s3')
    def test_resize_unique_path(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image()), 'ContentType': 'image/jpeg'}
        event = {'bucket': 'test', 'key': 'test.jpg', 'original_key': 'test.jpg', 'processing_id': 'abc123'}
        response = resize_handler(event, {})
        self.assertEqual(response['key'], 'resized/abc123/test.jpg')

    @patch('src.steps.store.app.s3')
    @patch('src.steps.store.app.table')
    def test_store_unique_path(self, mock_table, mock_s3):
        event = {
            'bucket': 'test', 'key': 'test.jpg', 'original_key': 'test.jpg', 'processing_id': 'abc123',
            'metadata': {'width': 10, 'height': 10, 'format': 'JPEG'}
        }
        response = store_handler(event, {})
        self.assertEqual(response['final_key'], 'processed/abc123/test.jpg')
        mock_table.put_item.assert_called_once()
        self.assertEqual(mock_table.put_item.call_args[1]['Item']['ProcessingId'], 'abc123')

    @patch('src.poller.app.sfn')
    @patch('src.poller.app.lock_table')
    @patch('time.time')
    def test_poller_lease_expires(self, mock_time, mock_table, mock_sfn):
        mock_time.return_value = 1000
        mock_table.put_item.side_effect = ClientError({'Error': {'Code': 'ConditionalCheckFailedException'}}, 'PutItem')
        
        # Return an item with an expired lease (e.g., 500)
        mock_table.get_item.return_value = {'Item': {'Status': 'PROCESSING', 'LeaseExpiry': 500}}
        
        event = {
            'Records': [{
                'messageId': '123',
                'body': '{"Records":[{"s3":{"bucket":{"name":"test"},"object":{"key":"test.jpg","versionId":"v1"}}}]}'
            }]
        }
        response = poller_handler(event, {})
        self.assertEqual(len(response['batchItemFailures']), 0)
        mock_table.update_item.assert_called_once()
        mock_sfn.start_execution.assert_called_once()

    @patch('src.poller.app.sfn')
    @patch('src.poller.app.lock_table')
    @patch('time.time')
    def test_poller_lease_active(self, mock_time, mock_table, mock_sfn):
        mock_time.return_value = 1000
        mock_table.put_item.side_effect = ClientError({'Error': {'Code': 'ConditionalCheckFailedException'}}, 'PutItem')
        
        # Return an item with a valid lease (e.g., 1500)
        mock_table.get_item.return_value = {'Item': {'Status': 'PROCESSING', 'LeaseExpiry': 1500}}
        
        event = {
            'Records': [{
                'messageId': '123',
                'body': '{"Records":[{"s3":{"bucket":{"name":"test"},"object":{"key":"test.jpg","versionId":"v1"}}}]}'
            }]
        }
        response = poller_handler(event, {})
        self.assertEqual(len(response['batchItemFailures']), 0)
        mock_table.update_item.assert_not_called()
        mock_sfn.start_execution.assert_not_called()

if __name__ == '__main__':
    unittest.main()
