try:
    import json
except ImportError:
    import simplejson as json

import requests

SYNC_MAX_TIMEOUT = 60*10

class SpireClientException(Exception):
    """Base class for spire client exceptions"""

class Client(object):
    def __init__(self, base_url, key=None, async=True):
        self.base_url = base_url
        self.key = key
        self.async = async
        self.resources = None
        self.schema = None
        self.notifications = None

    def get_session(self):
        # TODO write a decorator that automatically discovers and starts a
        # session if one is not present.
        if self.async:
            pass
        else:
            if not self.resources or not self.schema:
                self._discover()
            return self._start_session()
        
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

        self.resources = discovery_result
        self.schema = discovery_result['schema']['1.0']['mimeTypes']

        return self.resources

    def _start_session(self):
        """Start a session and set self.notifications. Requires discovery to
        have been called. TODO decorator that sets discovery"""
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
            raise SpireClientException("Could not create session")
        try:
            parsed = json.loads(response.content)
        except (ValueError, KeyError):
            raise SpireClientException("Spire endpoint returned invalid JSON")
        return Session(self, parsed['url'], parsed['channels']['url'])


    def _discover_async(self):
        pass

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
    def __init__(self, client, url, channels_url):
        self.url = url
        self.channels_url = channels_url
        self.client = client # has the schema and notification urls on it

    def channel(self, channel_name=None): # None is the root channel
        data = {}
        if channel_name:
            data['name'] = channel_name
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

        return Channel(self.client, parsed['url'], name=parsed.get('name', None))

class Channel(object):
    # For now we will let users handle subchannels themselves using dot
    # notation. At some point managing the channel tree in the library would be
    # neat.
    def __init__(self, client, url, name=None):
        self.client = client
        self.url = url
        self.name = name

        self.subscriptions = {}

    def _create_subscription(self, filter=None):
        content_type = self.client.schema['subscription']

        data = {}
        if self.name is not None:
            data['name'] = self.name
        response = requests.post(
            self.url,
            headers={'Accept': content_type, 'Content-type': content_type},
            data=json.dumps(data),
            )

        return json.loads(response.content)

    def subscribe(self, filter=None):
        url = self.subscriptions.get(filter, None)
        if url is None:
            url = self._create_subscription(filter)['url']

        if self.client.async:
            # this first pass is all synchronous, i should probably stop
            # pretending like i've got the sync/async switching figured out
            # until I get the basic functionality working sync but I can't help
            # leaving myself little notes like this
            def _callback():
                pass
            self._on(url, _callback)
        else:
            return self._wait_for_message(url, filter=filter)

    def _wait_for_message(self, url, filter=None):
        # synchronous. long timeouts, reopen connections when they die
        response = None
        tries = 0
        while not response and tries < 5: # TODO remove tries
            tries = tries + 1
            # todo throttle fast reconnects

            params = dict(
                headers={'Accept': self.client.schema['events']},
                timeout=SYNC_MAX_TIMEOUT,
                )
            if self.name is not None:
                params['data'] = dict(channel=self.channel_name)
            response = requests.get(url, **params)

        return json.loads(response.content)
            
    def publish(self, message):
        content_type = self.client.schema['message']
        params = dict(
            headers={'Accept': content_type, 'Content-type': content_type},
            data=json.dumps(dict(message=message)),
            )
        response = requests.post(self.url, **params)
        return json.loads(response.content)
