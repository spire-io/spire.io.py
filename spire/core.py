try:
    import json
except ImportError:
    import simplejson as json

import requests

try:
    from requests import async as r_async
except ImportError:
    pass

SYNC_MAX_TIMEOUT = 60*10

class SpireClientException(Exception):
    """Base class for spire client exceptions"""


def require_discovery(func):
    """Does what it sounds like it does. A decorator that can be applied to
    instance methods of Client to ensure discovery has been called"""
    # such lovely explicit naming!
    def decorated_instance_method(*args, **kwargs):
        # in instance methods, arg[0] will always be self
        zelf = args[0]
        if not zelf.resources or not zelf.schema:
            zelf._discover() # synchronous!
        return func(*args, **kwargs)
    return decorated_instance_method

class Client(object):
    def __init__(self, base_url, key=None, async=True):
        self.base_url = base_url
        self.key = key
        self.resources = None
        self.schema = None
        self.notifications = None
        self.async = async
        
    def _discover(self):
        response = requests.get(
            self.base_url,
            headers={'Accept':'application/json'},
            )

        if not response:
            raise SpireClientException("Spire discovery failed")
        try:
            discovery_result = json.loads(response.content)
        except ValueError:
            raise SpireClientException("Spire endpoint returned invalid JSON")

        def _check_schema(schema):
            return True # todo json schema or iterate over kvs

        if not _check_schema(discovery_result):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        self.resources = discovery_result['resources']
        self.schema = discovery_result['schema']['1.0']['mimeTypes']

        return self.resources

    @require_discovery
    def session(self):
        """Start a session and set self.notifications."""
        # synchronous!
        response = requests.post(
            self.resources['sessions']['url'],
            headers={
                'Accept': self.schema['session'],
                'Content-type': self.schema['account'],
                },
            data=json.dumps(dict(key=self.key)),
            )
        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not create session: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        return Session(self, parsed['url'], parsed['channels']['url'], parsed['subscriptions']['url'])


    def _discover_async(self):
        pass

    @require_discovery
    def create_account(self):
        # discover decorator
        response = requests.post(
            self.resources['accounts']['url'],
            headers={
                'Accept': self.schema['account'],
                'Content-type': self.schema['account'],
                },
            data=json.dumps({}),
            )
        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not create account")
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")
        self.key = parsed['key']
        return parsed
        

class Session(object):
    def __init__(self, client, url, channels_url, subscriptions_url):
        self.url = url
        self.channels_url = channels_url
        self.subscriptions_url = subscriptions_url
        self.client = client # has the schema and notification urls on it

    def channel(self, name=None, description=None): # None is the root channel
        # TODO move this into the channel class to avoid repetition
        data = {}
        if name is not None:
            data['name'] = name
        if description is not None:
            data['description'] = description

        response = requests.post(
            self.channels_url,
            headers={
                'Accept': self.client.schema['channel'],
                'Content-type': self.client.schema['channel'],
                },
            data=json.dumps(data),
            )

        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not create channel")
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        return Channel(self, parsed['url'], name=parsed.get('name', None))

class Channel(object):
    # For now we will let users handle subchannels themselves using dot
    # notation. At some point managing the channel tree in the library would be
    # neat.
    def __init__(self, session, url, name=None):
        self.session = session
        self.url = url
        self.name = name

        self.subscriptions = {}

    def subchannel(self, name):
        # TODO this should be in initialization
        if not self.name:
            raise SpireClientException("Cannot create subchannels of the root channel!")
        response = requests.post(
            self.session.channels_url,
            headers={
                'Accept': self.session.client.schema['channel'],
                'Content-type': self.session.client.schema['channel'],
                },
            data=json.dumps(dict(name="%s.%s" % (self.name, name))),
            )
            
        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not create channel")
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        return Channel(self.session, parsed['url'], name=parsed['name'])

    def _create_subscription(self, filter=None):
        response = requests.post(
            self.session.subscriptions_url,
            headers={
                'Accept': self.session.client.schema['subscription'],
                'Content-type': self.session.client.schema['subscription'],
                },
            data=json.dumps(dict(
                    channels=[self.url],
                    events='messages',
                    )),
            )
        parsed = json.loads(response.content)
        self.subscriptions[filter] = parsed['url']
        return parsed

    def subscribe(self, filter=None, callback=None):
        url = self.subscriptions.get(filter, None)
        if url is None:
            url = self._create_subscription(filter)['url']

        if self.session.client.async:
            # TODO decoratorize this
            if callback is None:
                raise SpireClientException("callbacks required in async mode")
            self._on(url, callback)
        else:
            return self._wait_for_message(url, filter=filter)

    def _on(self, url, callback):
        assert self.session.client.async
        # todo handle reconnects in async mode
        def _callback(response):
            # TODO error handling for async
            parsed = json.loads(response.content)
            callback(parsed['messages'])
        request = r_async.get(
            url,
            headers={'Accept': self.session.client.schema['events']},
            hooks=dict(response=_callback),
            )
        r_async.map([request])

    def _wait_for_message(self, url, filter=None):
        # synchronous. long timeouts, reopen connections when they die
        response = None
        tries = 0
        while not response and tries < 5: # TODO remove tries
            tries = tries + 1
            # todo throttle fast reconnects
            response = requests.get(
                url,
                headers={'Accept': self.session.client.schema['events']},
                timeout=SYNC_MAX_TIMEOUT,
                )
        return json.loads(response.content)['messages']
            
    def publish(self, message):
        content_type = self.session.client.schema['message']
        response = requests.post(
            self.url,
            headers={'Accept': content_type, 'Content-type': content_type},
            data=json.dumps(dict(message=message)),
            )

        return json.loads(response.content)
