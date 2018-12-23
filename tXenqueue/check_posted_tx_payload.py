# This code adapted by RJH Sept 2018 from door43-enqueue-job
#       and from tx-manager/client_webhook/ClientWebhookHandler

# Local imports
from tx_enqueue_helpers import get_gogs_user


COMPULSORY_FIELDNAMES = 'job_id', 'user_token', \
                'resource_type', 'input_format', 'output_format', 'source'
OPTIONAL_FIELDNAMES = 'callback', 'identifier', 'options', 'door43_webhook_received_at'
ALL_FIELDNAMES = COMPULSORY_FIELDNAMES + OPTIONAL_FIELDNAMES
OPTION_SUBFIELDNAMES = 'columns', 'css', 'language', 'line_spacing', \
                        'page_margins', 'page_size', 'toc_levels'

# NOTE: The following are currently only used to log warnings -- they are not strictly enforced here
KNOWN_RESOURCE_TYPES = ( 'Bible', 'Aligned_Bible', 'Greek_New_Testament', 'Hebrew_Old_Testament',
                'Translation_Academy', 'Translation_Notes', 'Translation_Questions', 'Translation_Words',
                'Open_Bible_Stories', 'OBS_Translation_Notes', 'OBS_Translation_Questions',
                'bible', 'book', 'obs', 'ta', 'tn', 'tq', 'tw', )
KNOWN_INPUT_FORMATS = 'md', 'usfm', 'txt'
KNOWN_OUTPUT_FORMATS = 'docx', 'html', 'pdf',


def check_posted_tx_payload(request, logger):
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

    # TODO: Should we check any headers ???
    #if 'X-Gogs-Event' not in request.headers:
        #logger.error(f"Cannot find 'X-Gogs-Event' in {request.headers}")
        #return False, {'error': 'This does not appear to be from DCS.'}

    # Get the json payload and check it
    payload_json = request.get_json()
    logger.info(f"tX payload is {payload_json}")

    # Check for existance of unknown fieldnames
    for some_fieldname in payload_json:
        if some_fieldname not in ALL_FIELDNAMES:
            logger.warning(f'Unexpected {some_fieldname} field in tX payload')

    # Check for existence of compulsory fieldnames
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

    # NOTE: We only treat unknown types as warnings -- the job handler has the authoritative list
    if payload_json['resource_type'] not in KNOWN_RESOURCE_TYPES:
        logger.warning(f"Unknown '{payload_json['resource_type']}' resource type in tX payload")
    if payload_json['input_format'] not in KNOWN_INPUT_FORMATS:
        logger.warning(f"Unknown '{payload_json['input_format']}' input format in tX payload")
    if payload_json['output_format'] not in KNOWN_OUTPUT_FORMATS:
        logger.warning(f"Unknown '{payload_json['output_format']}' output format in tX payload")

    if 'options' in payload_json:
        for some_option_fieldname in payload_json['options']:
            if some_option_fieldname not in OPTION_SUBFIELDNAMES:
                logger.warning(f'Unexpected {some_option_fieldname} option field in tX payload')

    # Check the gogs/gitea user token
    if len(payload_json['user_token']) != 40:
        logger.error(f"Invalid user token '{payload_json['user_token']}' in tX payload")
        return False, {'error': f"Invalid user token '{payload_json['user_token']}'"}
    user = get_gogs_user(payload_json['user_token'])
    logger.info(f"Found Gogs user: {user}")
    if not user:
        logger.error(f"Unknown user token '{payload_json['user_token']}' in tX payload")
        return False, {'error': f"Unknown user token '{payload_json['user_token']}'"}

    logger.info("tX payload seems ok")
    return True, payload_json
# end of check_posted_tx_payload
