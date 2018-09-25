# Adapted by RJH June 2018 from fork of https://github.com/lscsoft/webhook-queue (Public Domain / unlicense.org)
#   The main change was to add some vetting of the json payload before allowing the job to be queued.
#   Updated Sept 2018 to add callback service

# TODO: We don't currently have any way to clear the failed queue

# Python imports
from os import getenv
import sys
from datetime import datetime, timedelta
import logging

# Library (PyPi) imports
from flask import Flask, request, jsonify
# NOTE: We use StrictRedis() because we don't need the backwards compatibility of Redis()
from redis import StrictRedis
from rq import Queue, Worker
from statsd import StatsClient # Graphite front-end

# Local imports
from check_posted_tx_payload import check_posted_tx_payload #, check_posted_callback_payload
from tx_enqueue_helpers import get_unique_job_id


OUR_NAME = 'tX_webhook' # Becomes the (perhaps prefixed) queue name (and graphite name) -- MUST match setup.py in tx-job-handler
#CALLBACK_SUFFIX = '_callback'

# NOTE: The following strings if not empty, MUST have a trailing slash but NOT a leading one.
WEBHOOK_URL_SEGMENT = '' # Leaving this blank will cause the service to run at '/'
#CALLBACK_URL_SEGMENT = WEBHOOK_URL_SEGMENT + 'callback/'

JOB_TIMEOUT = '200s' # Then a running job (taken out of the queue) will be considered to have failed
    # NOTE: This is only the time until webhook.py returns after submitting the jobs
    #           -- the actual conversion jobs might still be running.


# Look at relevant environment variables
prefix = getenv('QUEUE_PREFIX', '') # Gets (optional) QUEUE_PREFIX environment variable -- set to 'dev-' for development
if prefix not in ('', 'dev-'):
    logging.critical(f"Unexpected prefix: {prefix!r} -- expected '' or 'dev-'")
if prefix:
    our_adjusted_name = prefix + OUR_NAME # Will become our main queue name
    other_our_adjusted_name = OUR_NAME # The other queue name
else:
    our_adjusted_name = OUR_NAME # Will become our main queue name
    other_our_adjusted_name = 'dev-'+OUR_NAME # The other queue name
# NOTE: The prefixed version must also listen at a different port (specified in gunicorn run command)
#our_callback_name = our_adjusted_name + CALLBACK_SUFFIX
#other_our_adjusted_callback_name = other_our_adjusted_name + CALLBACK_SUFFIX


# Enable DEBUG logging for dev- instances (but less logging for production)
logging.basicConfig(level=logging.DEBUG if prefix else logging.ERROR)

prefix_string = f" with prefix {prefix!r}" if prefix else ""
logging.info(f"enqueueMain.py running on Python v{sys.version}{prefix_string}")


# Get the redis URL from the environment, otherwise use a local test instance
redis_hostname = getenv('REDIS_HOSTNAME', 'redis')
logging.info(f"redis_hostname is {redis_hostname!r}")

# Get the Graphite URL from the environment, otherwise use a local test instance
graphite_url = getenv('GRAPHITE_HOSTNAME', 'localhost')
logging.info(f"graphite_url is {graphite_url!r}")
stats_client = StatsClient(host=graphite_url, port=8125, prefix=our_adjusted_name)


TX_JOB_CDN_BUCKET = 'https://cdn.door43.org/tx/jobs/'



app = Flask(__name__)


## This code is for debugging only and can be removed
#@app.route('/showDB/', methods=['GET'])
#def show_DB():
    #"""
    #Display a helpful status list to a user connecting to our debug URL.
    #"""
    #r = StrictRedis(host=redis_hostname)
    #result_string = f'This {OUR_NAME} enqueuing service has:'

    ## Look at environment variables
    #result_string += '<h1>Environment Variables</h1>'
    #result_string += f"<p>QUEUE_PREFIX={getenv('QUEUE_PREFIX', '(not set)=>(no prefix)')}</p>"
    #result_string += f"<p>FLASK_ENV={getenv('FLASK_ENV', '(not set)=>(normal/production)')}</p>"
    #result_string += f"<p>REDIS_HOSTNAME={getenv('REDIS_HOSTNAME', '(not set)=>redis')}</p>"
    #result_string += f"<p>GRAPHITE_HOSTNAME={getenv('GRAPHITE_HOSTNAME', '(not set)=>localhost')}</p>"

    ## Look at all the potential queues
    #for this_our_adjusted_name in (OUR_NAME, 'dev-'+OUR_NAME, 'failed'):
        #q = Queue(this_our_adjusted_name, connection=r)
        #queue_output_string = ''
        ##queue_output_string += '<p>Job IDs ({0}): {1}</p>'.format(len(q.job_ids), q.job_ids)
        #queue_output_string += f'<p>Jobs ({len(q.jobs)}): {q.jobs}</p>'
        #result_string += f'<h1>{this_our_adjusted_name} queue:</h1>{queue_output_string}'

    #if redis_hostname == 'redis': # Can't do this for production redis (too many keys!!!)
        ## Look at the raw keys
        #keys_output_string = ''
        #for key in r.scan_iter():
            #keys_output_string += '<p>' + key.decode() + '</p>\n'
        #result_string += f'<h1>All keys ({len(r.keys())}):</h1>{keys_output_string}'

    #return result_string
## end of show_DB()


# This is the main workhorse part of this code
#   rq automatically returns a "Method Not Allowed" error for a GET, etc.
@app.route('/'+WEBHOOK_URL_SEGMENT, methods=['POST'])
def job_receiver():
    """
    Accepts POST requests and checks the (json) payload

    Queues the approved jobs at redis instance at global redis_hostname:6379.
    Queue name is our_adjusted_name (may have been prefixed).
    """
    if request.method == 'POST':
        stats_client.incr('TotalPostsReceived')
        logging.info(f"Enqueue received request: {request}")
        response_ok_flag, response_dict = check_posted_tx_payload(request) # response_dict is json payload if successful, else error info

        if response_ok_flag:
            # Collect (and log) some helpful information
            stats_client.incr('GoodPostsReceived')
            redis_connection = StrictRedis(host=redis_hostname)
            our_queue = Queue(our_adjusted_name, connection=redis_connection)
            len_our_queue = len(our_queue)
            stats_client.gauge(prefix+'QueueLength', len_our_queue)
            failed_queue = Queue('failed', connection=redis_connection)
            len_failed_queue = len(failed_queue)
            stats_client.gauge('FailedQueueLength', len_failed_queue)

            # Extend the given payload (dict) to add our required fields
            our_response_dict = dict(response_dict)
            our_response_dict.update({ \
                                'job_id': get_unique_job_id(),
                                'success':'true',
                                'status':'queued',
                                'queue_name':our_adjusted_name,
                                'queued_at':datetime.utcnow(),
                                })
            if 'identifier' not in our_response_dict:
                our_response_dict['identifier'] = our_response_dict['job_id']
            our_response_dict['output'] = f"{TX_JOB_CDN_BUCKET}{our_response_dict['job_id']}.zip"
            our_response_dict['expires_at'] = our_response_dict['queued_at'] + timedelta(days=1)
            our_response_dict['eta'] = our_response_dict['queued_at'] + timedelta(minutes=5)
            logging.debug(f"About to queue job: {our_response_dict}")

            # NOTE: No ttl specified on the next line -- this seems to cause unrun jobs to be just silently dropped
            #           (For now at least, we prefer them to just stay in the queue if they're not getting processed.)
            #       The timeout value determines the max run time of the worker once the job is accessed
            our_queue.enqueue('webhook.job', our_response_dict, timeout=JOB_TIMEOUT) # A function named webhook.job will be called by the worker
            # NOTE: The above line can return a result from the webhook.job function. (By default, the result remains available for 500s.)

            # Find out who our workers are
            #workers = Worker.all(connection=redis_connection) # Returns the actual worker objects
            #logging.debug(f"Total rq workers ({len(workers)}): {workers}")
            #our_queue_workers = Worker.all(queue=our_queue)
            #logging.debug(f"Our {our_adjusted_name} queue workers ({len(our_queue_workers)}): {our_queue_workers}")

            # Find out how many workers we have
            #worker_count = Worker.count(connection=redis_connection)
            #logging.debug(f"Total rq workers = {worker_count}")
            #our_queue_worker_count = Worker.count(queue=our_queue)
            #logging.debug(f"Our {our_adjusted_name} queue workers = {our_queue_worker_count}")

            other_queue = Queue(other_our_adjusted_name, connection=redis_connection)
            logging.info(f'{OUR_NAME} queued valid job to {our_adjusted_name} ' \
                        f'({len_our_queue} jobs now ' \
                            f'for {Worker.count(queue=our_queue)} workers, ' \
                        f'{len(other_queue)} jobs in {other_our_adjusted_name} queue ' \
                            f'for {Worker.count(queue=other_queue)} workers, ' \
                        f'{len_failed_queue} failed jobs) at {datetime.utcnow()}')
            return jsonify(our_response_dict)
        else:
            stats_client.incr('InvalidPostsReceived')
            response_dict['status'] = 'failed'
            logging.error(f'{OUR_NAME} ignored invalid payload; responding with {response_dict}')
            return jsonify(response_dict), 400
# end of job_receiver()


#@app.route('/'+CALLBACK_URL_SEGMENT, methods=['POST'])
#def callback_receiver():
    #"""
    #Accepts POST requests and checks the (json) payload

    #Queues the approved jobs at redis instance at global redis_hostname:6379.
    #Queue name is our_callback_name (may have been prefixed).
    #"""
    #if request.method == 'POST':
        #stats_client.incr('TotalCallbackPostsReceived')
        #logging.info(f"Enqueue received callback request: {request}")
        #response_ok_flag, response_dict = check_posted_callback_payload(request) # response_dict is json payload if successful, else error info

        #if response_ok_flag:
            ## Collect (and log) some helpful information
            #stats_client.incr('GoodCallbackPostsReceived')
            #redis_connection = StrictRedis(host=redis_hostname)
            #our_queue = Queue(our_callback_name, connection=redis_connection)
            #len_our_queue = len(our_queue)
            #stats_client.gauge(prefix+'QueueLength', len_our_queue)
            #failed_queue = Queue('failed', connection=redis_connection)
            #len_failed_queue = len(failed_queue)
            #stats_client.gauge('FailedQueueLength', len_failed_queue)
            ## NOTE: No ttl specified on the next line -- this seems to cause unrun jobs to be just silently dropped
            ##           (For now at least, we prefer them to just stay in the queue if they're not getting processed.)
            ##       The timeout value determines the max run time of the worker once the job is accessed
            #our_queue.enqueue('callback.job', response_dict, timeout=JOB_TIMEOUT) # A function named callback.job will be called by the worker
            ## NOTE: The above line can return a result from the callback.job function. (By default, the result remains available for 500s.)

            #other_callback_queue = Queue(other_our_adjusted_callback_name, connection=redis_connection)

            ## Find out who our workers are
            ##workers = Worker.all(connection=redis_connection) # Returns the actual worker objects
            ##logging.debug(f"Total rq workers ({len(workers)}): {workers}")
            ##our_queue_workers = Worker.all(queue=our_queue)
            ##logging.debug(f"Our {our_callback_name} queue workers ({len(our_queue_workers)}): {our_queue_workers}")

            ## Find out how many workers we have
            ##worker_count = Worker.count(connection=redis_connection)
            ##logging.debug(f"Total rq workers = {worker_count}")
            ##our_queue_worker_count = Worker.count(queue=our_queue)
            ##logging.debug(f"Our {our_callback_name} queue workers = {our_queue_worker_count}")

            #info_message = f'{OUR_NAME} queued valid callback job to {our_callback_name} ' \
                        #f'({len_our_queue} jobs now ' \
                            #f'for {Worker.count(queue=our_queue)} workers, ' \
                        #f'{len(other_callback_queue)} jobs in {other_our_adjusted_callback_name} queue ' \
                            #f'for {Worker.count(queue=other_callback_queue)} workers, ' \
                        #f'{len_failed_queue} failed jobs) at {datetime.utcnow()}'
            #logging.info(info_message)
            #return f'{OUR_NAME} queued valid callback job to {our_callback_name} at {datetime.utcnow()}'
        #else:
            #stats_client.incr('InvalidCallbackPostsReceived')
            #error_message = f'{OUR_NAME} ignored invalid callback payload; responding with {response_dict}'
            #logging.error(error_message)
            #return error_message, 400
## end of callback_receiver()


if __name__ == '__main__':
    app.run()
