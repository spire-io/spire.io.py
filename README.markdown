Spire
=====
http://spire.io

This is a Python `spire.io` client library

Here's an example using the message service.

    client = spire.Client(async=False, key=key) # key is your account key
    session = client.session()
    channel = session.channel('foo', 'the foo channel')
    channel.publish('What hath Shark wrought?')
    
Let's create a second session and get our messages.

    client2 = spire.Client(async=False, key=key) # key is your account key
    session2 = client2.session()
    channel2 = session2.channel('foo', 'the foo channel')
    channel2.subscribe() # => 'What hath Shark wrought?'
    
You can also assign listener blocks to a subscription which will be called with each message received:

    client3 = spire.Client(async=False, key=key) # key is your account key
    session3 = client3.session()
    channel3 = session3.channel('foo', 'the foo channel')
    
    def get_callback(channel_name):
        def _callback(messages):
            print messages
        return _callback

    channel3.subscribe(callback=get_callback("foo"))


Dependencies
------------

(up-to-date dependencies will always be in setup.py)

- [Requests](http://pypi.python.org/pypi/requests) is the only external dependency on Python 2.6+
- If you are running Python 2.5, you will need to install [simplejson](http://pypi.python.org/pypi/simplejson/)
- Asynchronous operation requires [gevent](http://pypi.python.org/pypi/gevent) (which in turn requires greenlet and libevent) - if you are running Debian or Ubuntu the system package (python-gevent) is recommended as installing from source via pip may lead to segfaults, and nobody likes those.
