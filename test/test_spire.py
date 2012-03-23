"""
Integration tests for the Spire client library. If the environment variable
SPIRE_SECRET (and optionally SPIRE_HOST) is set, they will run against the
remote API, otherwise a (currently broken) stub API will be used.
"""

import os
import re
import unittest
try:
    import json
except ImportError:
    import simplejson as json

from nose import SkipTest
from nose.tools import eq_ as eq

import stubserver

import spire

"""
These constants are meant to be used in the stub server when the tests are run
without a connection to the actual Spire service. The stub server isn't
currently set up to work, though.
"""

DISCOVERY = {}

NEW_SESSION = {}

class TestSpireClient(unittest.TestCase):
    def setUp(self):
        self.client, self.server = self.get_client()
        if self.server is not None:
            self.server.run()

    def get_client(self, async=False):
        spire_secret =  os.environ.get('SPIRE_SECRET', None)
        if spire_secret is not None:
            server = None
            client = spire.Client(
                os.environ.get('SPIRE_HOST', 'https://api.spire.io'),
                secret = spire_secret,
                async=async,
                )
        else:
            stub_port = 3133
            server = stubserver.StubServer(stub_port)
            client = spire.Client(
                "http://localhost/%i" % stub_port,
                async=async,
                )
        return (client, server)

    def tearDown(self):
        if self.server:
            self.server.stop() # stop also verifies calls

    def test_session_creation_and_implicit_discovery(self):
        if self.server:
            # I am not in love with the API of stubserver, but it sure beats
            # writing my own right now.
            #
            # Furthermore, these expectations aren't working the way I expect
            # them to. Leaving them here as documentation for the pattern I
            # want to follow in future tests
            self.server.expect(
                method='GET',
                url="/$").and_return(
                mime_type='application/json',
                content=json.dumps(DISCOVERY),
                )
            self.server.expect(
                method='POST',
                url=DISCOVERY['resources']['sessions']['url'],
                ).and_return(
                mime_type=DISCOVERY['schema']['1.0']['mimeTypes'],
                content=json.dumps(NEW_SESSION),
                )

        # Discovery hasn't happened
        assert self.client.resources is None
        assert self.client.schema is None

        session = self.client.session()

        assert isinstance(session, spire.Session)
        eq(session.client, self.client)

        # Discovery has happened
        assert session.client.resources is not None
        assert session.client.schema is not None

    def test_create_and_publish_to_default_channel(self):
        first_client_channel = self.client.session().channel()
        second_client_channel = self.get_client()[0].session().channel()
        assert first_client_channel.session != second_client_channel.session
        first_client_channel.publish('picture yourself on a boat on a river')

        messages = second_client_channel.subscribe()
        eq(
            [x['content'] for x in messages][:1],
            ['picture yourself on a boat on a river'],
            )

        first_client_channel.publish('with tangerine trees and marmalade skies')

        messages = second_client_channel.subscribe(last_timestamp=0)
        eq(
            [x['content'] for x in messages][:2],
            ['with tangerine trees and marmalade skies', 'picture yourself on a boat on a river'],
            )

    def test_create_and_publish_to_default_channel_evented(self):
        self.client, self.server = self.get_client(async=True)

        first_client_channel = self.client.session().channel()
        second_client_channel = self.get_client(async=True)[0].session().channel()
        assert first_client_channel.session != second_client_channel.session
        first_client_channel.publish('picture yourself on a boat on a river')

        def _first_channel(messages):
            eq(
                [x['content'] for x in messages][:1],
                ['picture yourself on a boat on a river'],
                )
            
        second_client_channel.subscribe(callback=_first_channel)

        first_client_channel.publish('with tangerine trees and marmalade skies')

        def _second_channel(messages):
            eq(
                [x['content'] for x in messages][:2],
                ['with tangerine trees and marmalade skies', 'picture yourself on a boat on a river'],
                )

        second_client_channel.subscribe(
            last_timestamp=0,
            callback=_second_channel,
            )

    def test_create_and_publish_to_named_channel(self):
        first_client_channel = self.client.session().channel('test-channel-name')
        second_client_channel = self.get_client()[0].session().channel('test-channel-name')
        assert first_client_channel.session != second_client_channel.session
        first_client_channel.publish('Do you want ants?')

        messages = second_client_channel.subscribe()
        eq(
            [x['content'] for x in messages][0],
            'Do you want ants?',
            )

        first_client_channel.publish("BECAUSE THAT'S HOW YOU GET ANTS")

        messages = second_client_channel.subscribe()
        eq(
            [x['content'] for x in messages][0],
            "BECAUSE THAT'S HOW YOU GET ANTS",
            )

    def test_channel_with_url_and_capability_only(self):
        # awkwardness = refactor opportunity
        session = self.client.session()
        channel = session.channel(name='keep-it-safe')

        unprivileged_client = spire.Client(
            os.environ.get('SPIRE_HOST', 'https://api.spire.io'),
            # Note lack of key
            )

        # would like to continue to refactor this to avoid discovering directly
        unprivileged_client._discover()
        unprivileged_channel = spire.Channel(
            unprivileged_client,
            None, # no session
            channel.channel_resource,
            )

        channel.publish('you blocked me on facebook - prepare to die')
        messages = channel.subscribe()
        eq(
            [x['content'] for x in messages][0],
            'you blocked me on facebook - prepare to die',
            )


    def test_subscription_with_url_and_capability_only(self):
        # awkwardness = refactor opportunity
        session = self.client.session()
        session._get_subscription_collection()
        channel = session.channel(name='keep-it-safe')
        subscription = session.subscription_collection.get('keep-it-safe', None)
        if subscription is None:
            subscription = channel._create_subscription(name='keep-it-safe')

        unprivileged_client = spire.Client(
            os.environ.get('SPIRE_HOST', 'https://api.spire.io'),
            # Note lack of key
            )

        # would like to continue to refactor this to avoid discovering directly
        unprivileged_client._discover()
        unprivileged_subscription = spire.Subscription(
            unprivileged_client,
            subscription.subscription_resource,
            )

        channel.publish('you blocked me on facebook - prepare to die')
        messages = unprivileged_subscription.subscribe()
        eq(
            [x['content'] for x in messages][0],
            'you blocked me on facebook - prepare to die',
            )

    def test_last_message_parameter(self):
        raise SkipTest

    def test_delete_channel(self):
        raise SkipTest
