# Adapted by RJH June 2018 from fork of https://github.com/lscsoft/webhook-queue (Public Domain / unlicense.org)
#   The main change was to add some vetting of the json payload before allowing the job to be queued.
#   Updated Sept 2018 to add callback service

# TODO: We don't currently have any way to clear the failed queue

"""
tX Enqueue Main

Accepts a JSON payload to start a convert (and in most cases, lint) process.
    check_posted_tx_payload.py does most of the payload content checking.

Expected JSON payload:
    job_id: any string to identify this particular job to the caller
    identifier: optional—any human readable string to help identify this particular job
    user_token: A 40-character Door43 Gogs/Gitea user token
    resource_type: one of 17 (as at Jan2020) strings to identify the input type
                            e.g., 'OBS_Study_Notes' with underlines not spaces.
    input_format: input file(s) format—one of 'md', 'usfm', 'txt', 'tsv'.
    output_format: desired output format—one of 'html', 'pdf', or eventually 'docx'.
    source: url of zip file containing the input files.
    callback: optional url of callback function to be notified upon completion.
    options: optional dict of option parameters (depending on output_format).

If the payload parses successfully, a response dict is created and added to the job queue.

A JSON response dict is immediately returned as a response to the caller:
    Response JSON: Contains all of the given fields from the payload, plus
        success: True to indicate that the job was queued
        status: 'queued'
        queue_name: '(dev-)tX_webhook' or '(dev-)tX_OBS_PDF_webhook' or '(dev-)tX_other_PDF_webhook'
        tx_job_queued_at: current date & time
        output: URL of zipfile or PDF where converted output will be able to be downloaded from
        expires_at: date & time when above output link may become invalid (one day later)
        eta: date & time when output is expected (5 minutes later)
        tx_retry_count: 0
"""

# Python imports
import sys
import logging
import boto3
import watchtower

from os import getenv, environ
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from redis import StrictRedis
from rq import Queue, Worker
from statsd import StatsClient # Graphite front-end

# Local imports
from check_posted_tx_payload import check_posted_tx_payload #, check_posted_callback_payload
from tx_enqueue_helpers import get_unique_job_id


OUR_NAME = 'tX_webhook' # Becomes the (perhaps prefixed) HTML queue name (and graphite name)
                        #   -- MUST match setup.py in tx-job-handler
OUR_OBS_PDF_NAME = 'tX_OBS_PDF_webhook'
OUR_OTHER_PDF_NAME = 'tX_other_PDF_webhook'
#CALLBACK_SUFFIX = '_callback'
DEV_PREFIX = 'dev-'

# NOTE: The following strings if not empty, MUST have a trailing slash but NOT a leading one.
WEBHOOK_URL_SEGMENT = '' # Leaving this blank will cause the service to run at '/'
#CALLBACK_URL_SEGMENT = WEBHOOK_URL_SEGMENT + 'callback/'


# Look at relevant environment variables
prefix = getenv('QUEUE_PREFIX', '') # Gets (optional) QUEUE_PREFIX environment variable—set to 'dev-' for development
prefixed_our_name = prefix + OUR_NAME


JOB_TIMEOUT = '900s' if prefix else '800s' # Then a running job (taken out of the queue) will be considered to have failed
    # NOTE: This is the time until webhook.py returns after running the jobs.
    #       T4T is definitely one of our largest/slowest resources to lint and convert

# Get the redis URL from the environment, otherwise use a local test instance
redis_hostname = getenv('REDIS_HOSTNAME', 'redis')
# Use this to detect test mode (coz logs will go into a separate AWS CloudWatch stream)
debug_mode_flag = 'gogs' not in redis_hostname # Typically set to something like 172.20.0.2
test_string = " (TEST)" if debug_mode_flag else ""


# Setup logging
logger = logging.getLogger(prefixed_our_name)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
logger.addHandler(sh)
aws_access_key_id = environ['AWS_ACCESS_KEY_ID']
aws_secret_access_key = environ['AWS_SECRET_ACCESS_KEY']
boto3_client = boto3.client("logs", aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key,
                        region_name='us-west-2')
test_mode_flag = getenv('TEST_MODE', '')
travis_flag = getenv('TRAVIS_BRANCH', '')
log_group_name = f"{'' if test_mode_flag or travis_flag else prefix}tX" \
                 f"{'_DEBUG' if debug_mode_flag else ''}" \
                 f"{'_TEST' if test_mode_flag else ''}" \
                 f"{'_TravisCI' if travis_flag else ''}"
watchtower_log_handler = watchtower.CloudWatchLogHandler(boto3_client=boto3_client,
                                                log_group_name=log_group_name,
                                                stream_name=prefixed_our_name)

logger.addHandler(watchtower_log_handler)
# Enable DEBUG logging for dev- instances (but less logging for production)
logger.setLevel(logging.DEBUG if prefix else logging.INFO)
logger.debug(f"Logging to AWS CloudWatch group '{log_group_name}' using key '…{aws_access_key_id[-2:]}'.")


# Setup queue variables
QUEUE_NAME_SUFFIX = '' # Used to switch to a different queue, e.g., '_1'
if prefix not in ('', DEV_PREFIX):
    logger.critical(f"Unexpected prefix: '{prefix}' — expected '' or '{DEV_PREFIX}'")
if prefix:
    our_adjusted_convertHTML_queue_name = prefix + OUR_NAME + QUEUE_NAME_SUFFIX # Will become our main queue name
    our_adjusted_convertOBSPDF_queue_name = prefix + OUR_OBS_PDF_NAME + QUEUE_NAME_SUFFIX # Will become our main queue name
    our_adjusted_convertOtherPDF_queue_name = prefix + OUR_OTHER_PDF_NAME + QUEUE_NAME_SUFFIX # Will become our main queue name
    our_other_adjusted_convertHTML_queue_name = OUR_NAME + QUEUE_NAME_SUFFIX # The other queue name
    our_other_adjusted_convertOBSPDF_queue_name = OUR_OBS_PDF_NAME + QUEUE_NAME_SUFFIX # The other queue name
    our_other_adjusted_convertOtherPDF_queue_name = OUR_OTHER_PDF_NAME + QUEUE_NAME_SUFFIX # The other queue name
else:
    our_adjusted_convertHTML_queue_name = OUR_NAME + QUEUE_NAME_SUFFIX # Will become our main queue name
    our_adjusted_convertOBSPDF_queue_name = OUR_OBS_PDF_NAME + QUEUE_NAME_SUFFIX # Will become our main queue name
    our_adjusted_convertOtherPDF_queue_name = OUR_OTHER_PDF_NAME + QUEUE_NAME_SUFFIX # Will become our main queue name
    our_other_adjusted_convertHTML_queue_name = DEV_PREFIX + OUR_NAME + QUEUE_NAME_SUFFIX # The other queue name
    our_other_adjusted_convertOBSPDF_queue_name = DEV_PREFIX + OUR_OBS_PDF_NAME + QUEUE_NAME_SUFFIX # The other queue name
    our_other_adjusted_convertOtherPDF_queue_name = DEV_PREFIX + OUR_OTHER_PDF_NAME + QUEUE_NAME_SUFFIX # The other queue name
# NOTE: The prefixed version must also listen at a different port (specified in gunicorn run command)
#our_callback_name = our_adjusted_convertHTML_queue_name + CALLBACK_SUFFIX
#our_other_adjusted_callback_name = our_other_adjusted_convertHTML_queue_name + CALLBACK_SUFFIX


prefix_string = f" with prefix '{prefix}'" if prefix else ""
logger.info(f"tx_enqueue_main.py{prefix_string}{test_string} running on Python v{sys.version}")


# Connect to Redis now so it fails at import time if no Redis instance available
logger.info(f"redis_hostname is '{redis_hostname}'")
logger.debug(f"{prefixed_our_name} connecting to Redis…")
redis_connection = StrictRedis(host=redis_hostname)
logger.debug("Getting total worker count in order to verify working Redis connection…")
total_rq_worker_count = Worker.count(connection=redis_connection)
logger.debug(f"Total rq workers = {total_rq_worker_count}")

# Get the Graphite URL from the environment, otherwise use a local test instance
graphite_url = getenv('GRAPHITE_HOSTNAME', 'localhost')
logger.info(f"graphite_url is '{graphite_url}'")
stats_prefix = f"tx.{'dev' if prefix else 'prod'}.enqueue-job"
stats_client = StatsClient(host=graphite_url, port=8125, prefix=stats_prefix)


TX_JOB_CDN_BUCKET = f'https://{prefix}cdn.door43.org/tx/job/'
PDF_CDN_BUCKET = f'https://{prefix}cdn.door43.org/u/'


app = Flask(__name__)
# Not sure that we need this Flask logging
# app.logger.addHandler(watchtower_log_handler)
# logging.getLogger('werkzeug').addHandler(watchtower_log_handler)
logger.info(f"{prefixed_our_name} is up and ready to go")



def handle_failed_queue(our_queue_name:str) -> int:
    """
    Go through the failed queue, and see how many entries originated from our queue.

    Of those, permanently delete any that are older than two weeks old.
    """
    failed_queue = Queue('failed', connection=redis_connection)
    len_failed_queue = len(failed_queue)
    if len_failed_queue:
        logger.debug(f"There are {len_failed_queue} total jobs in failed queue")

    len_our_failed_queue = 0
    for failed_job in failed_queue.jobs.copy():
        if failed_job.origin == our_queue_name:
            failed_duration = datetime.utcnow() - failed_job.enqueued_at
            if failed_duration >= timedelta(weeks=2):
                logger.info(f"Deleting expired '{our_queue_name}' failed job from {failed_job.enqueued_at}")
                failed_job.delete() # .cancel() doesn't delete the Redis hash
            else:
                len_our_failed_queue += 1

    if len_our_failed_queue:
        logger.info(f"Have {len_our_failed_queue} of our jobs in failed queue")
    return len_our_failed_queue
# end of handle_failed_queue function


# This is the main workhorse part of this code
#   rq automatically returns a "Method Not Allowed" error for a GET, etc.
@app.route('/'+WEBHOOK_URL_SEGMENT, methods=['POST'])
def job_receiver():
    """
    Accepts POST requests and checks the (json) payload

    Queues the approved jobs at redis instance at global redis_hostname:6379.
    Queue name is our_adjusted_convertHTML_queue_name (may have been prefixed).
    """
    #assert request.method == 'POST'
    stats_client.incr('posts.attempted')
    logger.info(f"tX {'('+prefix+')' if prefix else ''} enqueue received request: {request}")

    # Collect and log some helpful information for all three queues
    HTML_queue = Queue(our_adjusted_convertHTML_queue_name, connection=redis_connection)
    len_HTML_queue = len(HTML_queue)
    stats_client.gauge('tx_job_handler.queue.length.current', len_HTML_queue)
    len_HTML_failed_queue = handle_failed_queue(our_adjusted_convertHTML_queue_name)
    stats_client.gauge('tx_job_handler.queue.length.failed', len_HTML_failed_queue)
    OBSPDF_queue = Queue(our_adjusted_convertOBSPDF_queue_name, connection=redis_connection)
    len_OBSPDF_queue = len(OBSPDF_queue)
    stats_client.gauge('obs_pdf.queue.length.current', len_OBSPDF_queue)
    len_OBSPDF_failed_queue = handle_failed_queue(our_adjusted_convertOBSPDF_queue_name)
    stats_client.gauge('obs_pdf.queue.OBSPDF.length.failed', len_OBSPDF_failed_queue)
    otherPDF_queue = Queue(our_adjusted_convertOtherPDF_queue_name, connection=redis_connection)
    len_otherPDF_queue = len(otherPDF_queue)
    stats_client.gauge('other_pdf.queue.length.current', len_otherPDF_queue)
    len_otherPDF_failed_queue = handle_failed_queue(our_adjusted_convertOtherPDF_queue_name)
    stats_client.gauge('other_pdf.queue.length.failed', len_otherPDF_failed_queue)

    # Find out how many workers we have
    total_worker_count = Worker.count(connection=redis_connection)
    logger.debug(f"Total rq workers = {total_worker_count}")
    queue1_worker_count = Worker.count(queue=HTML_queue)
    logger.debug(f"Our {our_adjusted_convertHTML_queue_name} queue workers = {queue1_worker_count}")
    stats_client.gauge('workers.HTML.available', queue1_worker_count)
    if queue1_worker_count < 1:
        logger.critical(f"{prefixed_our_name} has no HTML job handler workers running!")
        # Go ahead and queue the job anyway for when a worker is restarted
    queue2_worker_count = Worker.count(queue=OBSPDF_queue)
    logger.debug(f"Our {our_adjusted_convertOBSPDF_queue_name} queue workers = {queue2_worker_count}")
    stats_client.gauge('workers.OBSPDF.available', queue2_worker_count)
    if queue2_worker_count < 1:
        logger.critical(f"{prefixed_our_name} has no OBSPDF job handler workers running!")
        # Go ahead and queue the job anyway for when a worker is restarted
    queue3_worker_count = Worker.count(queue=otherPDF_queue)
    logger.debug(f"Our {our_adjusted_convertOtherPDF_queue_name} queue workers = {queue3_worker_count}")
    stats_client.gauge('workers.otherPDF.available', queue3_worker_count)
    if queue3_worker_count < 1:
        logger.critical(f"{prefixed_our_name} has no otherPDF job handler workers running!")
        # Go ahead and queue the job anyway for when a worker is restarted

    response_ok_flag, response_dict = check_posted_tx_payload(request, logger)
    # response_dict is json payload if successful, else error info
    if response_ok_flag:
        logger.debug("tX_job_receiver processing good payload…")

        our_job_id = response_dict['job_id'] if 'job_id' in response_dict \
                        else get_unique_job_id()

        # Determine which worker to queue this request for
        if response_dict['output_format'] == 'html':
            job_type, not_job_type = 'HTML', 'PDF'
            our_adjusted_queue_name = our_adjusted_convertHTML_queue_name
            our_other_adjusted_queue_name = our_other_adjusted_convertHTML_queue_name
            our_adjusted_queue_name2 = our_adjusted_convertOBSPDF_queue_name
            our_other_adjusted_queue_name2 = our_other_adjusted_convertOBSPDF_queue_name
            our_adjusted_queue_name3 = our_adjusted_convertOtherPDF_queue_name
            our_other_adjusted_queue_name3 = our_other_adjusted_convertOtherPDF_queue_name
            our_queue = HTML_queue
            expected_output_URL = f"{TX_JOB_CDN_BUCKET}{our_job_id}.zip"
        elif response_dict['output_format'] == 'pdf':
            not_job_type = 'HTML'
            our_adjusted_queue_name2 = our_adjusted_convertHTML_queue_name
            our_other_adjusted_queue_name2 = our_other_adjusted_convertHTML_queue_name

            # Try to guess where the output PDF will end up
            expected_output_URL = 'UNKNOWN'
            if 'identifier' in response_dict \
            and '/' not in response_dict['identifier']:
                if response_dict['identifier'].count('--') == 2:
                    # Expected identifier in form '<repo_owner_username>/<repo_name>--<branch_or_tag_name>'
                    #  e.g. 'unfoldingWord/en_obs--v1'
                    logger.debug("Using1 'identifier' field to determine expected_output_URL…")
                    repo_owner_username, repo_name, branch_or_tag_name = response_dict['identifier'].split('--')
                    expected_output_URL = f"{PDF_CDN_BUCKET}{repo_owner_username}/{repo_name}/{branch_or_tag_name}/{response_dict['identifier']}.pdf"
                elif response_dict['identifier'].count('--') == 3:
                    # Expected identifier in form '<repo_owner_username>/<repo_name>--<branch_name>--<commit_hash>'
                    #  e.g. 'unfoldingWord/en_obs--master--7dac1e5ba2'
                    logger.debug("Using2 'identifier' field to determine expected_output_URL…")
                    repo_owner_username, repo_name, branch_or_tag_name, _commit_hash = response_dict['identifier'].split('--')
                    expected_output_URL = f"{PDF_CDN_BUCKET}{repo_owner_username}/{repo_name}/{branch_or_tag_name}/{repo_owner_username}--{repo_name}--{branch_or_tag_name}.pdf"
            elif response_dict['source'].count('/') == 6 \
            and response_dict['source'].endswith('.zip'):
                # Expected URL in form 'https://git.door43.org/<repo_owner_username>/<repo_name>/archive/<branch_or_tag_name>.zip'
                #  e.g. 'https://git.door43.org/unfoldingWord/en_obs/archive/master.zip'
                logger.debug("Using 'source' field to determine expected_output_URL…")
                parts = response_dict['source'][:-4].split('/') # Remove the .zip first
                if len(parts) != 7:
                    logger.critical(f"Source field is in unexpected form: '{response_dict['source']}' -> {parts}.zip")
                expected_output_URL = f"{PDF_CDN_BUCKET}{parts[3]}/{parts[4]}/{parts[6]}/{parts[3]}--{parts[4]}--{parts[6]}"
            logger.info(f"Got expected_output_URL = {expected_output_URL}")

            # Determine the correct PDF creation queue
            if response_dict['resource_type'] == 'Open_Bible_Stories': # subject
                job_type = 'OBS-PDF'
                our_adjusted_queue_name = our_adjusted_convertOBSPDF_queue_name
                our_other_adjusted_queue_name = our_other_adjusted_convertOBSPDF_queue_name
                our_adjusted_queue_name3 = our_adjusted_convertOtherPDF_queue_name
                our_other_adjusted_queue_name3 = our_other_adjusted_convertOtherPDF_queue_name
                our_queue = OBSPDF_queue
            else: # not OBS
                job_type = 'other-PDF'
                our_adjusted_queue_name = our_adjusted_convertOtherPDF_queue_name
                our_other_adjusted_queue_name = our_other_adjusted_convertOtherPDF_queue_name
                our_adjusted_queue_name3 = our_adjusted_convertOBSPDF_queue_name
                our_other_adjusted_queue_name3 = our_other_adjusted_convertOBSPDF_queue_name
                our_queue = otherPDF_queue

        # Extend the given payload (dict) to add our required fields
        #logger.debug("Building our response dict…")
        our_response_dict = dict(response_dict)
        our_response_dict.update({ \
                            'success': True,
                            'status': 'queued',
                            'queue_name': our_adjusted_queue_name,
                            'tx_job_queued_at': datetime.utcnow(),
                            })
        if 'job_id' not in our_response_dict:
            our_response_dict['job_id'] = our_job_id
        if 'identifier' not in our_response_dict:
            our_response_dict['identifier'] = our_job_id
        our_response_dict['output'] = expected_output_URL
        our_response_dict['expires_at'] = our_response_dict['tx_job_queued_at'] + timedelta(days=1)
        our_response_dict['eta'] = our_response_dict['tx_job_queued_at'] + timedelta(minutes=5)
        our_response_dict['tx_retry_count'] = 0
        logger.debug(f"About to queue {job_type} job: {our_response_dict}")

        # NOTE: No ttl specified on the next line—this seems to cause unrun jobs to be just silently dropped
        #           (For now at least, we prefer them to just stay in the queue if they're not getting processed.)
        #       The timeout value determines the max run time of the worker once the job is accessed
        our_queue.enqueue('webhook.job', our_response_dict, job_timeout=JOB_TIMEOUT) # A function named webhook.job will be called by the worker
        # NOTE: The above line can return a result from the webhook.job function. (By default, the result remains available for 500s.)

        # Find out who our workers are
        #workers = Worker.all(connection=redis_connection) # Returns the actual worker objects
        #logger.debug(f"Total rq workers ({len(workers)}): {workers}")
        #our_queue_workers = Worker.all(queue=our_queue)
        #logger.debug(f"Our {our_adjusted_queue_name} queue workers ({len(our_queue_workers)}): {our_queue_workers}")

        # Find out how many workers we have
        #worker_count = Worker.count(connection=redis_connection)
        #logger.debug(f"Total rq workers = {worker_count}")
        #our_queue_worker_count = Worker.count(queue=our_queue)
        #logger.debug(f"Our {our_adjusted_queue_name} queue workers = {our_queue_worker_count}")

        len_our_queue = len(our_queue) # Update
        other_queue = Queue(our_other_adjusted_queue_name, connection=redis_connection)
        queue2 = Queue(our_adjusted_queue_name2, connection=redis_connection)
        other_queue2 = Queue(our_other_adjusted_queue_name2, connection=redis_connection)
        queue3 = Queue(our_adjusted_queue_name3, connection=redis_connection)
        other_queue3 = Queue(our_other_adjusted_queue_name3, connection=redis_connection)
        logger.info(f"{prefixed_our_name} queued valid {job_type} job to {our_adjusted_queue_name} queue " \
                    f"({len_our_queue} {job_type} jobs now " \
                        f"for {Worker.count(queue=our_queue)} workers, " \
                    f"{len(other_queue)} {job_type} jobs in {our_other_adjusted_queue_name} queue " \
                        f"for {Worker.count(queue=other_queue)} workers, " \
                    f"{len_HTML_failed_queue} failed {job_type} jobs), " \
                    f"({len(queue2)} {not_job_type} jobs in {our_adjusted_queue_name2} queue, " \
                    f"{len(other_queue2)} {not_job_type} jobs in {our_other_adjusted_queue_name2} queue) " \
                    f"({len(queue3)} {not_job_type} jobs in {our_adjusted_queue_name3} queue, " \
                    f"{len(other_queue3)} {not_job_type} jobs in {our_other_adjusted_queue_name3} queue) " \
                    f"at {datetime.utcnow()}\n")
        stats_client.incr('posts.succeeded')
        return jsonify(our_response_dict)
    else:
        stats_client.incr('posts.invalid')
        response_dict['status'] = 'invalid'
        logger.error(f"{prefixed_our_name} ignored invalid payload; responding with {response_dict}\n")
        return jsonify(response_dict), 400
# end of job_receiver()


if __name__ == '__main__':
    app.run()
