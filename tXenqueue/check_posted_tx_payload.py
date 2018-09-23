# This code adapted by RJH Sept 2018 from door43-enqueue-job
#       and from tx-manager/client_webhook/ClientWebhookHandler

import logging


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

    # TODO: What payload info do we need to check here?
    ## Bail if the URL to the repo is invalid
    #try:
        #if not payload_json['repository']['html_url'].startswith(GOGS_URL):
            #logging.error(f"The repo at {payload_json['repository']['html_url']!r} does not belong to {GOGS_URL!r}")
            #return False, {'error': f'The repo does not belong to {GOGS_URL}.'}
    #except KeyError:
        #logging.error("No repo URL specified")
        #return False, {'error': 'No repo URL specified.'}

    ## Bail if the commit branch is not the default branch
    #try:
        #commit_branch = payload_json['ref'].split('/')[2]
    #except (IndexError, AttributeError):
        #logging.error(f"Could not determine commit branch from {payload_json['ref']}")
        #return False, {'error': 'Could not determine commit branch.'}
    #except KeyError:
        #logging.error("No commit branch specified")
        #return False, {'error': 'No commit branch specified.'}
    #try:
        #if commit_branch != payload_json['repository']['default_branch']:
            #logging.error(f'Commit branch: {commit_branch} is not the default branch')
            #return False, {'error': f'Commit branch: {commit_branch} is not the default branch.'}
    #except KeyError:
        #logging.error("No default branch specified")
        #return False, {'error': 'No default branch specified.'}

    # TODO: Check why this code was commented out in tx-manager -- if it's not necessary let's delete it
    # Check that the user token is valid
    #if not App.gogs_user_token:
        #raise Exception('DCS user token not given in Payload.')
    #user = App.gogs_handler().get_user(App.gogs_user_token)
    #if not user:
        #raise Exception('Invalid DCS user token given in Payload')

    logging.info("Payload seems ok")
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
