import os
import sys

try:
    import json
except ImportError:
    import simplejson as json

import requests

try:
    from requests import async as r_async
except ImportError:
    pass

SUBSCRIBE_MAX_TIMEOUT = 30
my_config = {}
if os.environ.get('REQUESTS_VERBOSE_LOGGING'):
    my_config['verbose'] = sys.stderr

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
    def __init__(self, base_url='http://api.spire.io', key=None, async=True):
        self.base_url = base_url
        self.key = key
        self.resources = None
        self.schema = None
        self.notifications = None
        self.async = async
        self.capability = None
        self._unused_sessions = []

    def _discover(self):
        response = requests.get(
            self.base_url,
            headers={'Accept':'application/json'},
            config=my_config,
            )

        if not response:
            raise SpireClientException("Spire discovery failed")
        try:
            discovery_result = json.loads(response.content)
            #YYY
            

        except ValueError:
            raise SpireClientException("Spire endpoint returned invalid JSON")

        def _check_schema(schema):
            return True # todo json schema or iterate over kvs

        if not _check_schema(discovery_result):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        self.resources = discovery_result['resources']
        
        self.schema = {}
        for key, value in discovery_result['schema']['1.0'].iteritems():
            self.schema[key] = value['mediaType']

        return self.resources

    @require_discovery
    def session(self):
        """Start a session and set self.notifications."""
        if self._unused_sessions:
            return self._unused_sessions.pop()
        # synchronous!
        response = requests.post(
            self.resources['sessions']['url'],
            headers={
                'Accept': self.schema['session'],
                'Content-type': self.schema['account'],
                },
            data=json.dumps(dict(key=self.key)),
            config=my_config,
            )
        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not create session: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        # This interface to Session is based on earlier versions of the session
        # schema. It might make more sense to initialize Session with
        # parsed['resources'] rather than the 3 arguments below. Then again,
        # passing them as arguments makes clear that they are the values
        # required to create a session, meaning we don't have to validate the
        # schema in Session (if we do any schema validation it should be before
        # creating the class, in my opinion/gut-feeling).
        capabilities = dict(session=parsed['capability'])
        for key, value in parsed['resources'].iteritems():
            capabilities[key] = value['capability']

        return Session(
            self,
            parsed['url'],
            parsed['resources']['channels']['url'],
            parsed['resources']['subscriptions']['url'],
            capabilities,
            )


    def _discover_async(self):
        pass

    @require_discovery
    def create_account(self, email, password):
        response = requests.post(
            self.resources['accounts']['url'],
            headers={
                'Accept': self.schema['session'],
                'Content-type': self.schema['account'],
                },
            data=json.dumps(dict(email=email, password=password)),
            config=my_config,
            )

        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not create account")
        try:
            parsed = json.loads(response.content)

        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")
        self.key = parsed['resources']['account']['key']
        capabilities = dict(session=parsed['capability'])
        for key, value in parsed['resources'].iteritems():
            capabilities[key] = value['capability']
        self._unused_sessions.append(
            Session(
                self,
                parsed['url'],
                parsed['resources']['channels']['url'],
                parsed['resources']['subscriptions']['url'],
                capabilities,
                ),
            )
        return True

class Session(object):
    def __init__(self, client, url, channels_url, subscriptions_url, capabilities):
        self.url = url
        self.channels_url = channels_url
        self.subscriptions_url = subscriptions_url
        self.client = client # has the schema and notification urls on it
        self.capabilities = capabilities

    def channel(self, name=None, description=None): # None is the root channel
        # TODO move this into the channel class to avoid repetition
        data = {}

        # The below is a workaround for a bug in Spire, and should be rendered
        # unnecessary before the next beta release
        if name is None:
            name = 'everyone'

        if name is not None:
            data['name'] = name
        if description is not None:
            data['description'] = description
            
        response = requests.post(
            self.channels_url,
            headers={
                'Accept': self.client.schema['channel'],
                'Content-type': self.client.schema['channel'],
                'Authorization': "Capability %s" % self.capabilities['channels'],
                },
            data=json.dumps(data),
            config=my_config,
            )

        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not create channel")
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        return Channel(self, parsed['url'], parsed['capability'], name=name)

class Channel(object):
    def __init__(self, session, url, capability, name=None):
        self.session = session
        self.url = url
        self.name = name
        self.capability = capability
        self.subscriptions = {}
        self.last_message_timestamp = None

    def _create_subscription(self, philter=None):
        response = requests.post(
            self.session.subscriptions_url,
            headers={
                'Accept': self.session.client.schema['subscription'],
                'Content-type': self.session.client.schema['subscription'],
                'Authorization': "Capability %s" % self.session.capabilities['subscriptions'],
                },
            data=json.dumps(dict(
                    channels=[self.url],
                    events='messages',
                    )),
            config=my_config,
            )
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not subscribe: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire subscription endpoint returned invalid JSON")

        self.subscriptions[philter] = parsed
        return parsed

    def subscribe(self, philter=None, last_message_timestamp=None, callback=None):
        subscription = self.subscriptions.get(philter, None)
        if subscription is None:
            subscription = self._create_subscription(philter)

        if self.session.client.async:
            # TODO decoratorize this
            if callback is None:
                raise SpireClientException("callbacks required in async mode")
            self._on(subscription, callback, last_message=last_message_timestamp)
        else:
            return self._wait_for_message(
                subscription,
                philter=philter,
                last_message_timestamp=last_message_timestamp,
                )

    def _on(self, url, callback, last_message_timestamp=None):
        assert self.session.client.async
        # todo handle reconnects in async mode
        def _callback(response):
            # TODO error handling for async
            parsed = json.loads(response.content)
            callback(parsed['messages'])

        params=dict(timeout=SUBSCRIBE_MAX_TIMEOUT)
        if last_message_timestamp is not None:
            params['last-message'] = str(last_message_timestamp)

        request = r_async.get(
            url,
            headers={'Accept': self.session.client.schema['events']},
            timeout=SUBSCRIBE_MAX_TIMEOUT+1,
            params=params,
            hooks=dict(response=_callback),
            )
        r_async.map([request])

    def _wait_for_message(
        self,
        subscription,
        philter=None,
        last_message_timestamp=None,
        ):
        # synchronous. long timeouts, reopen connections when they die
        response = None
        tries = 0
        params=dict(timeout=SUBSCRIBE_MAX_TIMEOUT)

        if last_message_timestamp is not None:
            self.last_message_timestamp = last_message_timestamp
        if self.last_message_timestamp is not None:
            params['last-message'] = last_message_timestamp

        while not response and tries < 5: # TODO remove tries
            tries = tries + 1
            # todo throttle fast reconnects
            response = requests.get(
                subscription['url'],
                headers={
                    'Accept': self.session.client.schema['events'],
                    'Authorization': "Capability %s" % subscription['capability'],
                    },
                timeout=SUBSCRIBE_MAX_TIMEOUT+1,
                params=params,
                config=my_config,
                )

        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not subscribe: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire subscribe endpoint returned invalid JSON")

        return parsed['messages']
            
    def publish(self, message):
        content_type = self.session.client.schema['message']

        response = requests.post(
            self.url,
            headers={
                'Accept': content_type,
                'Content-type': content_type,
                'Authorization': "Capability %s" % self.capability,
                },
            data=json.dumps(dict(content=message)),
            config=my_config,
            )

        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not publish: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire channel endpoint returned invalid JSON")
        
        return parsed
