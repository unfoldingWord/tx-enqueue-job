# tX-Enqueue-Job

This (shorter) README was for the Docker Hub long description (but that doesn't actually work in Docker it seems).

This container is part of tX translationConverter platform initiated by a POST request to
 [tx.org???](https://tx.org/???).

See [here](https://forum.ccbt.bible/t/door43-org-tx-development-architecture/65)
for a diagram of the overall flow of the tx (translationConverter) platform.


## tX modifications of original repository

Modified June 2018 by RJH mainly to add vetting of the json payload
before the job is added to the redis queue.

Also added Graphite stats collection (using statsd package)
and viewable with Grafana.

Basically this small program collects the json payload from the tX (Translation
Converter Service) which connects to the `/` URL.

This enqueue process checks for various fields for simple validation of the
payload, and then puts the job onto a (rq) queue (stored in redis) to be
processed.

There is also a callback service connected to the `tx-callback/` URL. (Notice the
trailing slash.) Callback jobs are placed onto a different queue.


The Python code is run in Flask, which is then served by Green Unicorn (gunicorn).
A nginx instance is expected to face the outside world.

The next part in the tx workflow can be found in the [tx-job-handler](https://github.com/unfoldingWord-dev/tx-job-handler)
repo. The job handler contains `webhook.py` (see below) which is given jobs
that have been removed from the queue and then processes them -- adding them
back to a `failed` queue if they give an exception or time-out. Note that the
queue name here in `enqueueMain.py` must match the one in the job handler `rq_settings.py`.
