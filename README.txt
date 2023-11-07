Installation
============

$> mkdir <microfarm project directory>
$> cd <microfarm project directory>
$> python3.10 -m venv .
$> source bin/activate
$> pip install -r services.txt


Get started
===========

$> cd <microfarm project directory>
$> source bin/activate


Account service
---------------

$> ./bin/mfaccounts serve config/service.accounts.toml


PKI service
-----------

$> ./bin/mfpki serve config/service.pki.toml
$> ./bin/mfpki work config/worker.pki.toml


JWT service
-----------

$> ./bin/mfjwt serve config/service.jwt.toml identities/jwt.key identities/jwt.pub


Mailing service
---------------

$> sudo python -m smtpd -c DebuggingServer -n localhost:25
$> ./bin/mfcourrier serve config/service.courrier.toml


Websocket service
-----------------

$> ./bin/mfwebsockets serve config/service.ws.toml identities/jwt.pub


HTTP API
--------

$> ./bin/sanic microfarm:app [--debug] [--single-process]


Web UI
------

$> cd src/microfarm-ui
$> yarn serve
