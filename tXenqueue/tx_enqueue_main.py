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


# Setup logging
logger = logging.getLogger()
sh = logging.StreamHandler(sys.stdout)
head = '%(asctime)s - %(levelname)s: %(message)s'
sh.setFormatter(logging.Formatter(head))
logger.addHandler(sh)
# Enable DEBUG logging for dev- instances (but less logging for production)
logger.setLevel(logging.DEBUG if prefix else logging.INFO)


# Setup queue variables
if prefix not in ('', 'dev-'):
    logger.critical(f"Unexpected prefix: {prefix!r} -- expected '' or 'dev-'")
if prefix:
    our_adjusted_name = prefix + OUR_NAME # Will become our main queue name
    other_our_adjusted_name = OUR_NAME # The other queue name
else:
    our_adjusted_name = OUR_NAME # Will become our main queue name
    other_our_adjusted_name = 'dev-'+OUR_NAME # The other queue name
# NOTE: The prefixed version must also listen at a different port (specified in gunicorn run command)
#our_callback_name = our_adjusted_name + CALLBACK_SUFFIX
#other_our_adjusted_callback_name = other_our_adjusted_name + CALLBACK_SUFFIX


prefix_string = f" with prefix {prefix!r}" if prefix else ""
logger.info(f"enqueueMain.py running on Python v{sys.version}{prefix_string}")


# Get the redis URL from the environment, otherwise use a local test instance
redis_hostname = getenv('REDIS_HOSTNAME', 'redis')
logger.info(f"redis_hostname is {redis_hostname!r}")
# And now connect so it fails at import time if no Redis instance available
logger.debug("tX_job_receiver() connecting to Redis...")
redis_connection = StrictRedis(host=redis_hostname)
logger.debug("Getting total worker count in order to verify working Redis connection...")
total_rq_worker_count = Worker.count(connection=redis_connection)
logger.debug(f"Total rq workers = {total_rq_worker_count}")

# Get the Graphite URL from the environment, otherwise use a local test instance
graphite_url = getenv('GRAPHITE_HOSTNAME', 'localhost')
logger.info(f"graphite_url is {graphite_url!r}")
stats_prefix = f"tx.{'dev' if prefix else 'prod'}.enqueue-job"
stats_client = StatsClient(host=graphite_url, port=8125, prefix=stats_prefix)


TX_JOB_CDN_BUCKET = 'https://cdn.door43.org/tx/jobs/'


app = Flask(__name__)
logger.info(f"{our_adjusted_name} is up and ready to go...")



# This is the main workhorse part of this code
#   rq automatically returns a "Method Not Allowed" error for a GET, etc.
@app.route('/'+WEBHOOK_URL_SEGMENT, methods=['POST'])
def job_receiver():
    """
    Accepts POST requests and checks the (json) payload

    Queues the approved jobs at redis instance at global redis_hostname:6379.
    Queue name is our_adjusted_name (may have been prefixed).
    """
    #assert request.method == 'POST'
    stats_client.incr('posts.attempted')
    logger.info(f"tX {'('+prefix+')' if prefix else ''} enqueue received request: {request}")

    # Collect and log some helpful information
    our_queue = Queue(our_adjusted_name, connection=redis_connection)
    len_our_queue = len(our_queue)
    stats_client.gauge('queue.length.current', len_our_queue)
    failed_queue = Queue('failed', connection=redis_connection)
    len_failed_queue = len(failed_queue)
    stats_client.gauge('queue.length.failed', len_failed_queue)

    # Find out how many workers we have
    total_worker_count = Worker.count(connection=redis_connection)
    logger.debug(f"Total rq workers = {total_worker_count}")
    our_queue_worker_count = Worker.count(queue=our_queue)
    logger.debug(f"Our {our_adjusted_name} queue workers = {our_queue_worker_count}")
    stats_client.gauge('workers.available', our_queue_worker_count)
    if our_queue_worker_count < 1:
        logger.critical(f'{our_adjusted_name} has no job handler workers running!')
        # Go ahead and queue the job anyway for when a worker is restarted

    response_ok_flag, response_dict = check_posted_tx_payload(request, logger)
    # response_dict is json payload if successful, else error info
    if response_ok_flag:
        logger.debug("tX_job_receiver processing good payload...")
        stats_client.incr('posts.succeeded')

        # Extend the given payload (dict) to add our required fields
        logger.debug("Building response dict...")
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
        our_response_dict['tx_retry_count'] = 0
        logger.debug(f"About to queue job: {our_response_dict}")

        # NOTE: No ttl specified on the next line -- this seems to cause unrun jobs to be just silently dropped
        #           (For now at least, we prefer them to just stay in the queue if they're not getting processed.)
        #       The timeout value determines the max run time of the worker once the job is accessed
        our_queue.enqueue('webhook.job', our_response_dict, timeout=JOB_TIMEOUT) # A function named webhook.job will be called by the worker
        # NOTE: The above line can return a result from the webhook.job function. (By default, the result remains available for 500s.)

        # Find out who our workers are
        #workers = Worker.all(connection=redis_connection) # Returns the actual worker objects
        #logger.debug(f"Total rq workers ({len(workers)}): {workers}")
        #our_queue_workers = Worker.all(queue=our_queue)
        #logger.debug(f"Our {our_adjusted_name} queue workers ({len(our_queue_workers)}): {our_queue_workers}")

        # Find out how many workers we have
        #worker_count = Worker.count(connection=redis_connection)
        #logger.debug(f"Total rq workers = {worker_count}")
        #our_queue_worker_count = Worker.count(queue=our_queue)
        #logger.debug(f"Our {our_adjusted_name} queue workers = {our_queue_worker_count}")

        len_our_queue = len(our_queue) # Update
        other_queue = Queue(other_our_adjusted_name, connection=redis_connection)
        logger.info(f'{OUR_NAME} queued valid job to {our_adjusted_name} ' \
                    f'({len_our_queue} jobs now ' \
                        f'for {Worker.count(queue=our_queue)} workers, ' \
                    f'{len(other_queue)} jobs in {other_our_adjusted_name} queue ' \
                        f'for {Worker.count(queue=other_queue)} workers, ' \
                    f'{len_failed_queue} failed jobs) at {datetime.utcnow()}')
        return jsonify(our_response_dict)
    else:
        stats_client.incr('posts.failed')
        response_dict['status'] = 'failed'
        logger.error(f'{OUR_NAME} ignored invalid payload; responding with {response_dict}')
        return jsonify(response_dict), 400
# end of job_receiver()


if __name__ == '__main__':
    app.run()
