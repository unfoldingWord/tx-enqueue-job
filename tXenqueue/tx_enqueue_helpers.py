import hashlib
from datetime import datetime

from gogs_tools.gogs_handler import GogsHandler

GOGS_URL = 'https://git.door43.org'
gogs_handler = GogsHandler(GOGS_URL)


def get_gogs_user(token):
    """
    Given a user token, return the Gogs user details if any.
    """
    return gogs_handler.get_user(token)


def get_unique_job_id():
    """
    :return string:
    """
    job_id = hashlib.sha256(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f").encode('utf-8')).hexdigest()
    #while TxJob.get(job_id):
        #job_id = hashlib.sha256(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f").encode('utf-8')).hexdigest()
    return job_id
# end of get_unique_job_id()

