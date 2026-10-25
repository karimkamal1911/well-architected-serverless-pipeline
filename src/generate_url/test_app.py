import unittest
from unittest.mock import patch
import os

os.environ['BUCKET_NAME'] = 'test-bucket'

from app import lambda_handler

class TestGenerateUrl(unittest.TestCase):
    
    @patch('app.s3_client.generate_presigned_url')
    def test_lambda_handler_success(self, mock_generate_url):
        mock_generate_url.return_value = "https://fake-s3-url.com"
        
        event = {
            "body": '{"file_extension": ".png"}'
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('upload_url', response['body'])
        self.assertIn('object_key', response['body'])
        mock_generate_url.assert_called_once()

    def test_lambda_handler_invalid_extension(self):
        event = {
            "body": '{"file_extension": ".exe"}'
        }
        
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        self.assertIn('Invalid file extension', response['body'])

if __name__ == '__main__':
    unittest.main()
