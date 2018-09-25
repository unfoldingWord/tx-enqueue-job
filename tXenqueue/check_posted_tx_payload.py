# This code adapted by RJH Sept 2018 from door43-enqueue-job
#       and from tx-manager/client_webhook/ClientWebhookHandler

import logging

# Local imports
from tx_enqueue_helpers import get_gogs_user


COMPULSORY_FIELDNAMES = 'user_token', 'resource_type', 'input_format', 'output_format', 'source'
OPTIONAL_FIELDNAMES = 'callback', 'options'
ALL_FIELDNAMES = COMPULSORY_FIELDNAMES + OPTIONAL_FIELDNAMES
OPTION_SUBFIELDNAMES = 'columns', 'css', 'language', 'line_spacing', 'page_margins', 'page_size', 'toc_levels'

# NOTE: The following are currently only used to log warnings -- they are not strictly enforced here
KNOWN_RESOURCE_TYPES = 'bible', 'obs', 'ta', 'tn', 'tq', 'tw'
KNOWN_INPUT_FORMATS = 'md', 'usfm'
KNOWN_OUTPUT_FORMATS = 'docx', 'html', 'pdf',


def check_posted_tx_payload(request):
    """
    Accepts POSTed conversion request.
        Parameter is a rq request object

    Returns a 2-tuple:
        True or False if payload checks out
        The payload that was checked or error dict
    """
    # Bail if this is not a POST with a payload
    if not request.data:
        logging.error("Received request but no payload found")
        return False, {'error': 'No payload found. You must submit a POST request'}

    # TODO: What headers do we need to check ???
    ## Bail if this is not from DCS
    #if 'X-Gogs-Event' not in request.headers:
        #logging.error(f"Cannot find 'X-Gogs-Event' in {request.headers}")
        #return False, {'error': 'This does not appear to be from DCS.'}

    ## Bail if this is not a push event
    #if not request.headers['X-Gogs-Event'] == 'push':
        #logging.error(f"X-Gogs-Event is not a push in {request.headers}")
        #return False, {'error': 'This does not appear to be a push.'}

    # Get the json payload and check it
    payload_json = request.get_json()
    print( "payload is", repr(payload_json))

    # Check for existance of unknown fieldnames
    for some_fieldname in payload_json:
        if some_fieldname not in ALL_FIELDNAMES:
            logging.warning(f'Unexpected {some_fieldname} field in tX payload')

    # Check for existance of compulsory fieldnames
    error_list = []
    for compulsory_fieldname in COMPULSORY_FIELDNAMES:
        if compulsory_fieldname not in payload_json:
            logging.error(f'Missing {compulsory_fieldname} in tX payload')
            error_list.append(f'Missing {compulsory_fieldname}')
        elif not payload_json[compulsory_fieldname]:
            logging.error(f'Empty {compulsory_fieldname} field in tX payload')
            error_list.append(f'Empty {compulsory_fieldname} field')
    if error_list:
        return False, {'error': ', '.join(error_list)}

    # NOTE: We only treat unknown types as warnings -- the job handling has the authoritative list
    if payload_json['resource_type'] not in KNOWN_RESOURCE_TYPES:
        logging.warning(f"Unknown {payload_json['resource_type']!r} resource type in tX payload")
    if payload_json['input_format'] not in KNOWN_INPUT_FORMATS:
        logging.warning(f"Unknown {payload_json['input_format']!r} input format in tX payload")
    if payload_json['output_format'] not in KNOWN_OUTPUT_FORMATS:
        logging.warning(f"Unknown {payload_json['output_format']!r} output format in tX payload")

    if 'options' in payload_json:
        for some_option_fieldname in payload_json['options']:
            if some_option_fieldname not in OPTION_SUBFIELDNAMES:
                logging.warning(f'Unexpected {some_option_fieldname} option field in tX payload')

    # Check the gogs/gitea user token
    if len(payload_json['user_token']) != 40:
        logging.error(f"Invalid user token {payload_json['user_token']!r} in tX payload")
        return False, {'error': f"Invalid user token {payload_json['user_token']!r}"}
    user = get_gogs_user(payload_json['user_token'])
    logging.info(f"Found Gogs user: {user}")
    if not user:
        logging.error(f"Unknown user token {payload_json['user_token']!r} in tX payload")
        return False, {'error': f"Unknown user token {payload_json['user_token']!r}"}

    logging.info("tX payload seems ok")
    return True, payload_json
# end of check_posted_tx_payload



#def check_posted_callback_payload(request):
    #"""
    #Accepts callback notification from TX.
        #Parameter is a rq request object

    #Returns a 2-tuple:
        #True or False if payload checks out
        #The payload that was checked or error dict
    #"""
    ## Bail if this is not a POST with a payload
    #if not request.data:
        #logging.error("Received request but no payload found")
        #return False, {'error': 'No payload found. You must submit a POST request'}

    ## TODO: What headers do we need to check ???
    ### Bail if this is not from tX
    ##if 'X-Gogs-Event' not in request.headers:
        ##logging.error(f"Cannot find 'X-Gogs-Event' in {request.headers}")
        ##return False, {'error': 'This does not appear to be from tX.'}

    ### Bail if this is not a push event
    ##if not request.headers['X-Gogs-Event'] == 'push':
        ##logging.error(f"X-Gogs-Event is not a push in {request.headers}")
        ##return False, {'error': 'This does not appear to be a push.'}

    ## Get the json payload and check it
    #payload_json = request.get_json()
    #print( "callback payload is", repr(payload_json))

    ## TODO: What payload info do we need to check and to match to a job
    ### Bail if the URL to the repo is invalid
    ##try:
        ##if not payload_json['repository']['html_url'].startswith(GOGS_URL):
            ##logging.error(f"The repo at {payload_json['repository']['html_url']!r} does not belong to {GOGS_URL!r}")
            ##return False, {'error': f'The repo does not belong to {GOGS_URL}.'}
    ##except KeyError:
        ##logging.error("No repo URL specified")
        ##return False, {'error': 'No repo URL specified.'}

    ### Bail if the commit branch is not the default branch
    ##try:
        ##commit_branch = payload_json['ref'].split('/')[2]
    ##except (IndexError, AttributeError):
        ##logging.error(f"Could not determine commit branch from {payload_json['ref']}")
        ##return False, {'error': 'Could not determine commit branch.'}
    ##except KeyError:
        ##logging.error("No commit branch specified")
        ##return False, {'error': 'No commit branch specified.'}
    ##try:
        ##if commit_branch != payload_json['repository']['default_branch']:
            ##logging.error(f'Commit branch: {commit_branch} is not the default branch')
            ##return False, {'error': f'Commit branch: {commit_branch} is not the default branch.'}
    ##except KeyError:
        ##logging.error("No default branch specified")
        ##return False, {'error': 'No default branch specified.'}

    #logging.info("Callback payload seems ok")
    #return True, payload_json
## end of check_posted_callback_payload
