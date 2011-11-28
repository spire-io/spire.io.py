Spire
=====

Client library for http://spire.io

Dependencies
------------

(up-to-date dependencies will always be in setup.py)

- [Requests](http://pypi.python.org/pypi/requests) is the only external dependency on Python 2.6+
- If you are running Python 2.5, you will need to install [simplejson](http://pypi.python.org/pypi/simplejson/)
- Asynchronous operation requires [gevent](http://pypi.python.org/pypi/gevent) (which in turn requires greenlet and libevent) - if you are running Debian or Ubuntu the system package (python-gevent) is recommended as installing from source via pip may lead to segfaults, and nobody likes those.
