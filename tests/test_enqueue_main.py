from os import getenv
from unittest import TestCase
#from unittest.mock import Mock
import json

from flask import Flask, request
from redis import exceptions as redis_exceptions

# NOTE: This import will fail if we don't have a working Redis instance
#from tXenqueue.tx_enqueue_main import app, OUR_NAME, WEBHOOK_URL_SEGMENT, redis_hostname


#app.config['TESTING'] = True
#client = app.test_client()


#class TestEnqueueMain(TestCase):

    #def test_invalid_url(self):
        #response = client.get('/whatever/')
        #self.assertEqual(response.status_code, 404)

    #def test_invalid_webhook_get(self):
        #response = client.get('/'+WEBHOOK_URL_SEGMENT)
        #self.assertEqual(response.status_code, 405)

    #def test_webhook_with_empty_payload(self):
        #if redis_hostname == 'redis': # Using a (missing) local instance so won't all work
            #with self.assertRaises(redis_exceptions.ConnectionError):
                #response = client.post('/'+WEBHOOK_URL_SEGMENT)
        #else: # non-local  instance of redis so it should all work and we should get a page back
            #response = client.post('/'+WEBHOOK_URL_SEGMENT)
            #self.assertEqual(response.status_code, 400)
            #self.assertEqual(response.headers['Content-Type'], 'application/json' )
            #response_dict = json.loads(response.data)
            #expected_dict = {'error': 'No payload found. You must submit a POST request', 'status':'failed'}
            #self.assertEqual(response_dict, expected_dict)

    #def test_webhook_with_bad_headers(self):
        #headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        #payload_json = {'something': 'anything',}
        #if redis_hostname == 'redis': # Using a (missing) local instance so won't all work
            #with self.assertRaises(redis_exceptions.ConnectionError):
                #response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
        #else: # non-local  instance of redis so it should all work and we should get a page back
            #response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
            #self.assertEqual(response.status_code, 400)
            #self.assertEqual(response.headers['Content-Type'], 'application/json' )
            #response_dict = json.loads(response.data)
            #expected_dict = {'error': 'No payload found. You must submit a POST request', 'status':'failed'}
            #self.assertEqual(response_dict, expected_dict)

    #def test_webhook_with_bad_payload(self):
        #headers = {'Content-type': 'application/json'}
        #payload_json = {'something': 'anything',}
        #if redis_hostname == 'redis': # Using a (missing) local instance so won't all work
            #with self.assertRaises(redis_exceptions.ConnectionError):
                #response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
        #else: # non-local  instance of redis so it should all work and we should get a page back
            #response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
            #self.assertEqual(response.status_code, 400)
            #self.assertEqual(response.headers['Content-Type'], 'application/json' )
            #expected = "tx ignored invalid payload; responding with {'error': 'No repo URL specified.'}"
            #self.assertEqual(response.data, expected.encode())

    ##def test_webhook_with_minimal_json_payload(self):
        ##headers = {'Content-type': 'application/json'}
        ##payload_json = {
            ##'user_token': 'fredfredfredfredfredfredfredfredfredfred',
            ##'resource_type': 'obs',
            ##'input_format': 'md',
            ##'output_format': 'pdf',
            ##'source': 'https://git.door43.org/unfoldingWord/en_obs/archive/v4.zip'
            ##}
        ##if redis_hostname == 'redis': # Using a (missing) local instance so won't all work
            ##with self.assertRaises(redis_exceptions.ConnectionError):
                ##response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
        ##else: # non-local  instance of redis so it should all work and we should get a page back
            ##response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
            ##self.assertEqual(response.status_code, 200)
            ##self.assertEqual(response.headers['Content-Type'], 'application/json' )
            ##response_dict = json.loads(response.data)
            ##self.assertEqual(response_dict['success'], 'true')
            ##self.assertEqual(response_dict['status'], 'queued')

    ##def test_webhook_with_typical_full_json_payload(self):
        ##headers = {'Content-type': 'application/json'}
        ##with open( 'tests/Resources/webhook_post.json', 'rt' ) as json_file:
            ##payload_json = json.load(json_file)
        ##if redis_hostname == 'redis': # Using a (missing) local instance so won't all work
            ##with self.assertRaises(redis_exceptions.ConnectionError):
                ##response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
        ##else: # non-local  instance of redis so it should all work and we should get a page back
            ##response = client.post('/'+WEBHOOK_URL_SEGMENT, data=json.dumps(payload_json), headers=headers)
            ##self.assertEqual(response.status_code, 200)
            ##self.assertEqual(response.headers['Content-Type'], 'application/json' )
            ##self.assertTrue('queued valid job to' in response.data.decode())
            ### After job has run, should update https://dev.tx.org/u/tx-manager-test-data/en-obs-rc-0.2/93829a566c/
