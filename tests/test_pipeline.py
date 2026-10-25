import unittest
from unittest.mock import patch, MagicMock
import os
import io
from PIL import Image

os.environ['BUCKET_NAME'] = 'test-bucket'
os.environ['DEST_BUCKET'] = 'dest-bucket'
os.environ['TABLE_NAME'] = 'test-table'
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
        event = {'bucket': 'test', 'key': 'test.jpg'}
        response = validate_handler(event, {})
        self.assertEqual(response['bucket'], 'test')

    @patch('src.steps.validate.app.s3')
    def test_validate_too_large(self, mock_s3):
        mock_s3.head_object.return_value = {'ContentLength': 15 * 1024 * 1024}
        event = {'bucket': 'test', 'key': 'test.jpg'}
        with self.assertRaises(ValueError):
            validate_handler(event, {})

    @patch('src.steps.resize.app.s3')
    def test_resize_success(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image()), 'ContentType': 'image/jpeg'}
        event = {'bucket': 'test', 'key': 'test.jpg', 'original_key': 'test.jpg'}
        response = resize_handler(event, {})
        self.assertIn('resized/', response['key'])

    @patch('src.steps.watermark.app.s3')
    def test_watermark_success(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'original_key': 'test.jpg'}
        response = watermark_handler(event, {})
        self.assertTrue(response['key'].endswith('.jpg'))

    @patch('src.steps.extract_metadata.app.s3')
    def test_metadata_success(self, mock_s3):
        mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: self.create_dummy_image())}
        event = {'bucket': 'test', 'key': 'test.jpg', 'original_key': 'test.jpg'}
        response = metadata_handler(event, {})
        self.assertEqual(response['metadata']['format'], 'JPEG')

    @patch('src.steps.store.app.s3')
    @patch('src.steps.store.app.table')
    def test_store_success(self, mock_table, mock_s3):
        event = {
            'bucket': 'test', 'key': 'test.jpg', 'original_key': 'test.jpg',
            'metadata': {'width': 10, 'height': 10, 'format': 'JPEG'}
        }
        response = store_handler(event, {})
        self.assertIn('processed/test.jpg', response['final_key'])
        
    @patch('src.poller.app.sfn_client')
    @patch('src.poller.app.table')
    def test_poller_success(self, mock_table, mock_sfn):
        event = {
            'Records': [{
                'messageId': '123',
                'body': '{"Records":[{"s3":{"bucket":{"name":"test"},"object":{"key":"test.jpg","eTag":"123"}}}]}'
            }]
        }
        response = poller_handler(event, {})
        self.assertEqual(len(response['batchItemFailures']), 0)
        mock_sfn.start_execution.assert_called_once()

if __name__ == '__main__':
    unittest.main()
