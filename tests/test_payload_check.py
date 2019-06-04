from unittest import TestCase
from unittest.mock import Mock
import json
import logging

from tXenqueue.check_posted_tx_payload import check_posted_tx_payload


class TestPayloadCheck(TestCase):

    def test_blank(self):
        payload_json = ''
        mock_request = Mock()
        mock_request.data = payload_json
        output = check_posted_tx_payload(mock_request, logging)
        expected = False, {
            'error': 'No payload found. You must submit a POST request'
        }
        self.assertEqual(output, expected)


    def test_missing_compulsory_fields(self):
        headers = {}
        payload_json = {'something':'whatever'}
        mock_request = Mock(**{'get_json.return_value':payload_json})
        mock_request.headers = headers
        mock_request.data = payload_json
        output = check_posted_tx_payload(mock_request, logging)
        expected = False, {
            'error': 'Missing job_id, Missing user_token, Missing resource_type, Missing input_format, Missing output_format, Missing source'
        }
        self.assertEqual(output, expected)
# end of class TestPayloadCheck
