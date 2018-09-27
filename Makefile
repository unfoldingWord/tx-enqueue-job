doc: clean_doc
	echo 'building docs...'
	cd docs && sphinx-apidoc --force -M -P -e -o source/ ../enqueue
	cd docs && make html

clean_doc:
	echo 'cleaning docs...'
	cd docs && rm -f source/enqueue
	cd docs && rm -f source/enqueue*.rst

dependencies:
	# It is recommended that a Python3 virtual environment be set-up before this point
	#  python3 -m venv venv
	#  source venv/bin/activate
	pip3 install --requirement tXenqueue/requirements.txt

# NOTE: The following optional environment variables can be set:
#	REDIS_HOSTNAME (can be omitted for testing if a local instance is running; port 6379 is assumed always)
#	GRAPHITE_HOSTNAME (defaults to localhost if missing)
#	QUEUE_PREFIX (set it to dev- for testing)
#	FLASK_ENV (can be set to "development" for testing)
test:
	PYTHONPATH="tXenqueue/" python3 -m unittest discover -s tests/

runFlask:
	# NOTE: For very preliminary testing only (unless REDIS_HOSTNAME is already set-up)
	# This runs the enqueue process in Flask (for development/testing)
	#   and then connect at 127.0.0.1:5000/
	# Usually won't get far because there is often no redis instance running
	QUEUE_PREFIX="dev-" FLASK_ENV="development" python3 tXenqueue/tx_enqueue_main.py

composeEnqueueRedis:
	# NOTE: For testing only (using the 'dev-' prefix)
	# This runs the tXenqueue and redis processes via nginx/gunicorn
	#   and then connect at 127.0.0.1:8090/
	#   and "rq worker --config settings_enqueue" can connect to redis at 127.0.0.1:6379
	docker-compose --file docker-compose-tXenqueue-redis.yaml build
	docker-compose --file docker-compose-tXenqueue-redis.yaml up

composeEnqueue:
	# NOTE: For testing only (using the 'dev-' prefix)
	# This runs the tXenqueue process via nginx/gunicorn
	#   and then connect at 127.0.0.1:8090/
	# It assumes redis is already running locally (usually from Door43-Enqueue_Job)
	#   and so "rq worker --config settings_enqueue" can connect to redis at 127.0.0.1:6379
	docker-compose --file docker-compose-tXenqueue.yaml build
	docker-compose --file docker-compose-tXenqueue.yaml up

imageDev:
	# NOTE: This build sets the prefix to 'dev-' and sets debug mode
	docker build --file tXenqueue/Dockerfile-developBranch --tag unfoldingword/tx_enqueue_job:develop tXenqueue

imageMaster:
	docker build --file tXenqueue/Dockerfile-masterBranch --tag unfoldingword/tx_enqueue_job:master tXenqueue

pushDevImage:
	# Expects to be already logged into Docker, i.e., docker login -u $(DOCKER_USERNAME)
	docker push unfoldingword/tx_enqueue_job:develop

pushMasterImage:
	# Expects to be already logged into Docker, i.e., docker login -u $(DOCKER_USERNAME)
	docker push unfoldingword/tx_enqueue_job:master

# NOTE: To test the container use:
# 	docker run --env QUEUE_PREFIX="dev-" --env FLASK_ENV="development" --env REDIS_HOSTNAME=<redis_hostname> --net="host" --name tx_enqueue_job --rm tx_enqueue_job


# NOTE: To run the container in production use with the desired values:
# 	docker run --env GRAPHITE_HOSTNAME=<graphite_hostname> --env REDIS_HOSTNAME=<redis_hostname> --net="host" --name tx_enqueue_job --rm tx_enqueue_job
