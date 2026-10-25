import unittest
from unittest.mock import patch
import os

# Set fake environment variables for the test
os.environ['BUCKET_NAME'] = 'test-bucket'

# Import the lambda handler
from app import lambda_handler

class TestGenerateUrl(unittest.TestCase):
    
    @patch('app.s3_client.generate_presigned_url')
    def test_lambda_handler_success(self, mock_generate_url):
        # Setup the mock to return a fake URL
        mock_generate_url.return_value = "https://fake-s3-url.com"
        
        # Create a fake event
        event = {
            "body": '{"file_extension": ".png"}'
        }
        
        # Call the function
        response = lambda_handler(event, {})
        
        # Assertions
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('upload_url', response['body'])
        self.assertIn('object_key', response['body'])
        mock_generate_url.assert_called_once()

if __name__ == '__main__':
    unittest.main()
