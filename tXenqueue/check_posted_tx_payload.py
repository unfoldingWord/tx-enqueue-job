# This code adapted by RJH Sept 2018 from door43-enqueue-job
#       and from tx-manager/client_webhook/ClientWebhookHandler

from typing import Dict, Tuple, Any
from os import getenv


# NOTE: The following are currently only used to log warnings -- they are not strictly enforced here
COMPULSORY_FIELDNAMES = 'job_id', \
                'resource_type', 'input_format', 'output_format', 'source', 'repo_name', 'repo_owner', 'repo_ref', \
                'repo_data_url', 'dcs_domain'
OPTIONAL_FIELDNAMES = 'user_token', \
                'callback', 'identifier', 'options', 'door43_webhook_received_at'
ALL_FIELDNAMES = COMPULSORY_FIELDNAMES + OPTIONAL_FIELDNAMES
OPTION_SUBFIELDNAMES = 'columns', 'css', 'language', 'line_spacing', \
                        'page_margins', 'page_size', 'toc_levels'

KNOWN_RESOURCE_SUBJECTS = ('Generic_Markdown',
            'Greek_Lexicon', 'Hebrew-Aramaic_Lexicon',
            # and 14 from https://api.door43.org/v3/subjects (last checked Mar 2020)
            'Bible', 'Aligned_Bible', 'Greek_New_Testament', 'Hebrew_Old_Testament',
            'Translation_Academy', 'Translation_Questions', 'Translation_Words',
            'Translation_Notes', 'TSV_Translation_Notes',
            'Open_Bible_Stories', 'OBS_Study_Notes', 'OBS_Study_Questions',
                                'OBS_Translation_Notes', 'OBS_Translation_Questions',
            )
            # A similar table also exists in door43-job-handler:webhook.py
KNOWN_INPUT_FORMATS = 'md', 'usfm', 'txt', 'tsv',
KNOWN_OUTPUT_FORMATS = 'docx', 'html', 'pdf',


# Get the redis URL from the environment, otherwise use a local test instance
redis_hostname = getenv('REDIS_HOSTNAME', 'redis')
# Use this to detect test mode (coz logs will go into a separate AWS CloudWatch stream)
debug_mode_flag = getenv('DEBUG_MODE', False)


def check_posted_tx_payload(request, logger) -> Tuple[bool, Dict[str,Any]]:
    """
    Accepts POSTed conversion request.
        Parameter is a rq request object

    Returns a 2-tuple:
        True or False if payload checks out
        The payload that was checked or error dict
    """
    logger.debug("check_posted_tx_payload()")

    # Bail if this is not a POST with a payload
    if not request.data:
        logger.error("Received request but no payload found")
        return False, {'error': 'No payload found. You must submit a POST request'}

    # Get the json payload and check it
    payload_json = request.get_json()
    logger.info(f"tX payload is {payload_json}")

    # Check for a test ping from Nagios
    if 'User-Agent' in request.headers and 'nagios-plugins' in request.headers['User-Agent'] \
    and not payload_json:
        return False, {'error': "This appears to be a Nagios ping for service availability testing."}

    # Warn on existence of unknown fieldnames (just makes interface debugging easier)
    for some_fieldname in payload_json:
        if some_fieldname not in ALL_FIELDNAMES:
            logger.warning(f'Unexpected {some_fieldname} field in tX payload')

    # Issue errors for non-existence of compulsory fieldnames and abort
    error_list = []
    for compulsory_fieldname in COMPULSORY_FIELDNAMES:
        if compulsory_fieldname not in payload_json:
            logger.error(f'Missing {compulsory_fieldname} in tX payload')
            error_list.append(f'Missing {compulsory_fieldname}')
        elif not payload_json[compulsory_fieldname]:
            logger.error(f'Empty {compulsory_fieldname} field in tX payload')
            error_list.append(f'Empty {compulsory_fieldname} field')
    if error_list:
        return False, {'error': ', '.join(error_list)}

    # NOTE: We only treat unknown values as warnings -- the job handler has the authoritative list
    if payload_json['resource_type'] not in KNOWN_RESOURCE_SUBJECTS:
        logger.warning(f"Unknown '{payload_json['resource_type']}' resource type in tX payload")
    if payload_json['input_format'] not in KNOWN_INPUT_FORMATS:
        logger.warning(f"Unknown '{payload_json['input_format']}' input format in tX payload")
    if payload_json['output_format'] not in KNOWN_OUTPUT_FORMATS:
        logger.warning(f"Unknown '{payload_json['output_format']}' output format in tX payload")

    if 'options' in payload_json:
        for some_option_fieldname in payload_json['options']:
            if some_option_fieldname not in OPTION_SUBFIELDNAMES:
                logger.warning(f'Unexpected {some_option_fieldname} option field in tX payload')

    if 'user_token' in payload_json: # now optional
        # Check the DCS user token
        if len(payload_json['user_token']) != 40:
            logger.error(f"Invalid DCS user token '{payload_json['user_token']}' in tX payload")
            return False, {'error': f"Invalid DCS user token '{payload_json['user_token']}'"}
        user = get_dcs_user(payload_json['user_token'])
        logger.info(f"Found DCS user: {user}")
        if not user:
            logger.error(f"Unknown DCS user token '{payload_json['user_token']}' in tX payload")
            return False, {'error': f"Unknown DCS user token '{payload_json['user_token']}'"}
    else: # no Gitea user token
        # Check the source of the request -- must be door43.org
        # print("Request headers:", request.headers)
        # if 'Host' in request.headers \
        if request.headers['Host'] == 'door43.org' \
        or request.headers['Host'].endswith('.door43.org'):
            logger.info(f"Accepted request from {request.headers['Host']}")
        elif debug_mode_flag \
        and request.headers['Host'] in ['127.0.0.1:80', 'tx-enqueue-job_proxy_1:80', 'txproxy:80']:
            logger.info(f"Accepted DEBUG request from {request.headers['Host']}")
        else:
            logger.error(f"No Gitea user token; rejected request from {request.headers['Host']}")
            return False, {'error': f"Missing Gitea user token in '{payload_json}'"}

    logger.info(f"tX payload for {payload_json['input_format']}➞{payload_json['output_format']} seems ok")
    return True, payload_json
# end of check_posted_tx_payload
