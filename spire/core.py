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
MAX_CHANNEL_CREATE_RETRIES = 3

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

        return Session(self, parsed)

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
        self._unused_sessions.append(Session(self, parsed))

        return True

def require_channnel_collection(func):
    """A decorator to fetch the channel collection if necessary"""
    def decorated_instance_method(*args, **kwargs):
        # in instance methods, arg[0] will always be self
        zelf = args[0]
        if not zelf.channel_collection:
            zelf._get_channel_collection() # synchronous!
        return func(*args, **kwargs)
    return decorated_instance_method

class Session(object):
    def __init__(self, client, session_resource):
        # TODO, simplify this from a bunch of args into just holding the whole
        # session dict and having some helper methods to extract juicy details
        # from it, like the other libraries
        self.client = client # has the schema and notification urls on it

        self.session_resource = session_resource
        self._channel_retries = {}
        self.channel_collection = None
        self.subscription_collection = None

    def _get_channel_collection(self):
        response = requests.get(
            self.session_resource['resources']['channels']['url'],
            headers={
                'Accept': self.client.schema['channels'],
                'Authorization': "Capability %s" % self.get_capability('channels'),
                },
            )
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not refresh session: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        self.channel_collection = parsed
        return parsed

    def _get_subscription_collection(self):
        response = requests.get(
            self.session_resource['resources']['subscriptions']['url'],
            headers={
                'Accept': self.client.schema['subscriptions'],
                'Authorization': "Capability %s" % self.get_capability('subscriptions'),
                },
            )
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not refresh session: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        self.subscription_collection = {}
        for key, resource in parsed.iteritems():
            self.subscription_collection[key] = Subscription(self, resource)

        return parsed

    def _refresh(self):
        # If another session creates a channel after we get our session, and we
        # try to create the same channel, it will return 409 Conflict. This
        # method fetches the session and updates the ivars
        #
        # This is copypasta from above. TODO: refactor requests and parsing
        response = requests.get(
            self.session_resource['url'],
            headers={
                'Accept': self.client.schema['session'],
                'Authorization': "Capability %s" % self.get_capability('session'),
                },
            )
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Could not refresh session: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")
        self.session_resource = parsed
        self._channel_retries = {}
        return True

    def get_capability(self, key):
        if key == 'session':
            return self.session_resource['capability']
        else:
            # TODO raise and handle exceptions here instead of returning None
            resource = self.session_resource['resources'].get(key, None)
            if resource:
                return resource.get('capability', None)
            else:
                return None

    @require_channnel_collection
    def set_channel(self, name, channel):
        self.channel_collection[name] = channel
        return channel

    @require_channnel_collection
    def get_channel(self, name):
        resource = self.channel_collection.get(name, None)
        if resource is not None:
            return Channel(self, resource) # cache objects
        else:
            return None

    def channel(self, name=None, description=None): # None is the root channel
        # Short circuit alert!
        channel = self.get_channel(name)
        if channel is not None:
            return channel

        # TODO move this into the channel class to avoid repetition
        data = {}

        # The below is a workaround for a bug in Spire, and should be rendered
        # unnecessary before the next beta release
        if name is None:
            name = 'everyone'

        data['name'] = name
        if description is not None:
            data['description'] = description

        response = requests.post(
            self.session_resource['resources']['channels']['url'],
            headers={
                'Accept': self.client.schema['channel'],
                'Content-type': self.client.schema['channel'],
                'Authorization': "Capability %s" % self.get_capability('channels'),
                },
            data=json.dumps(data),
            config=my_config,
            )

        # TODO: DRY this up
        if not response: # XXX response is also falsy for 4xx
            retries = self._channel_retries.get(name, 0)
            if response.status_code == 409 and retries < MAX_CHANNEL_CREATE_RETRIES:
                self._refresh()
                self._channel_retries[name] = retries + 1
                return self.channel(name, description)
            else:
                raise SpireClientException("Could not create channel")
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")

        channel = Channel(self, parsed)
        self.set_channel(name, channel)
        return channel

def require_subscription_collection(func):
    """A decorator to fetch the parent session's subscription collection if
    necessary. I do not like having this decorator walk up to self.session to
    do this work. It could use a minor redesign but this library needs to work
    when the next version of the API is deployed :)"""
    def decorated_instance_method(*args, **kwargs):
        # in instance methods, arg[0] will always be self
        zelf = args[0]
        if not zelf.session.subscription_collection:
            zelf.session._get_subscription_collection() # synchronous!
        return func(*args, **kwargs)
    return decorated_instance_method

class Channel(object):
    def __init__(self, session, channel_resource):
        self.session = session
        self.channel_resource = channel_resource
        self.last_message_timestamp = None

    @require_subscription_collection
    def _create_subscription(self, name=None):
        if name is None:
            name = 'default'
        response = requests.post(
            self.session.session_resource['resources']['subscriptions']['url'],
            headers={
                'Accept': self.session.client.schema['subscription'],
                'Content-type': self.session.client.schema['subscription'],
                'Authorization': "Capability %s" % self.session.get_capability('subscriptions'),
                },
            data=json.dumps(dict(
                    channels=[self.channel_resource['url']],
                    events='messages',
                    name=name,
                    )),
            config=my_config,
            )
        if not response: # XXX response is also falsy for 4xx
            # if response.status_code == 409:
            #     pass
            # else:
            raise SpireClientException("Could not subscribe: %i" % response.status_code)
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire subscription endpoint returned invalid JSON")

        subscription = Subscription(self.session, parsed) # boooo
        self.session.subscription_collection[name] = subscription
        return subscription_collection

    @require_subscription_collection
    def subscribe(self, name=None, last_message_timestamp=None, callback=None):
        if name is None:
            name = "default-%s" % self.channel_resource['key']
        subscription = self.session.subscription_collection.get(name, None)
        if subscription is None:
            subscription = self._create_subscription(name=name)

        return self._on(
            subscription,
            last_message_timestamp=last_message_timestamp,
            callback=callback,
            )

    def _on(
        self,
        subscription,
        last_message_timestamp=None,
        callback=None,
        ):
        """
        If `callback` is not present, this is synchronous with long timeouts,
        and connections that are reopened when they die. If `callback` *is*
        present, we attempt to use requests' gevent support.

        This method is a proxy for the Subscription class'
        `subscribe` method.
        """
        return subscription.subscribe(
            last_message_timestamp=last_message_timestamp,
            callback=callback,
            )

    def delete(self):
        response = requests.delete(
            self.channel_resource['url'],
            headers={
                'Authorization': "Capability %s" % self.channel_resource['capability'],
                },
            )
        if not response: # XXX response is also falsy for 4xx
            raise SpireClientException("Failed to delete channel: %i" % response.status_code)


    def publish(self, message):
        content_type = self.session.client.schema['message']

        response = requests.post(
            self.channel_resource['url'],
            headers={
                'Accept': content_type,
                'Content-type': content_type,
                'Authorization': "Capability %s" % self.channel_resource['capability'],
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

class Subscription(object):
    def __init__(self, session, subscription_resource):
        self.session = session
        self.subscription_resource = subscription_resource
        self.last_message_timestamp = None

    def subscribe(
        self,
        last_message_timestamp=None,
        callback=None,
        ):
        response = None
        tries = 0
        params = {
            "timeout": SUBSCRIBE_MAX_TIMEOUT,
            "order-by": "asc",
            }

        request_kwargs = dict(
            headers={
                'Accept': self.session.client.schema['events'],
                'Authorization': "Capability %s" % self.subscription_resource['capability'],
                },
            timeout=SUBSCRIBE_MAX_TIMEOUT+1,
            params=params,
            config=my_config,
            )

        if last_message_timestamp is None:
            if not self.last_message_timestamp:
                self.last_message_timestamp = 0
        else:
            self.last_message_timestamp = last_message_timestamp

        params['last-message'] = self.last_message_timestamp

        if callback is not None:
            assert self.session.client.async
            def wrapped_callback(response):
                try:
                    parsed = json.loads(response.content)
                except (ValueError, KeyError):
                    raise SpireClientException("Spire subscribe endpoint returned invalid JSON")
                return callback(parsed['messages'])

            request_kwargs['hooks'] = dict(response=wrapped_callback)
            request = r_async.get(self.subscription_resource['url'], **request_kwargs)
            r_async.map([request])
            return True
        else:
            while not response and tries < 5: # TODO remove tries
                tries = tries + 1
                # todo throttle fast reconnects
                response = requests.get(self.subscription_resource['url'], **request_kwargs)

            # TODO: DRY this up
            # TODO: 409 handling here
            if not response: # XXX response is also falsy for 4xx
                raise SpireClientException("Could not subscribe: %i" % response.status_code)
            try:
                parsed = json.loads(response.content)
            except (ValueError, KeyError):
                raise SpireClientException("Spire subscribe endpoint returned invalid JSON")
            for message in parsed['messages']:
                if message['timestamp'] > self.last_message_timestamp:
                    self.last_message_timestamp = message['timestamp']

            return parsed['messages']
