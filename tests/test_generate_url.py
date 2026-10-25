import unittest
from unittest.mock import patch
import os
import json

os.environ['BUCKET_NAME'] = 'test-bucket'
os.environ['FRONTEND_ORIGIN'] = 'https://example.com'

from src.generate_url.app import lambda_handler

class TestGenerateUrl(unittest.TestCase):
    @patch('src.generate_url.app.s3_client')
    def test_lambda_handler_success(self, mock_s3):
        mock_s3.generate_presigned_post.return_value = {"url": "https://fake-s3-url.com", "fields": {}}
        event = {"body": '{"file_extension": ".png"}'}
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['headers']['Access-Control-Allow-Origin'], 'https://example.com')
        self.assertIn('url', response['body'])
        mock_s3.generate_presigned_post.assert_called_once()

    @patch('src.generate_url.app.s3_client')
    def test_lambda_handler_invalid_extension(self, mock_s3):
        event = {"body": '{"file_extension": ".exe"}'}
        response = lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        self.assertEqual(response['headers']['Access-Control-Allow-Origin'], 'https://example.com')
        self.assertIn('Invalid file extension', response['body'])
