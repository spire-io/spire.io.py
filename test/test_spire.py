"""
Integration tests for the Spire client library. If the environment variable
SPIRE_KEY (and optionally SPIRE_HOST) is set, they will run against the
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

DISCOVERY = {
    "resources": {
        "accounts": {
            "url": "http://localhost:3133/accounts"
            }, 
        "sessions": {
            "url": "http://localhost:3133/sessions"
            }
        }, 
    "schema": {
        "1.0": {
            "mimeTypes": {
                "account": "application/vnd.spire-io.account+json;version=1.0", 
                "accounts": "application/vnd.spire-io.accounts+json;version=1.0", 
                "channel": "application/vnd.spire-io.channel+json;version=1.0", 
                "channels": "application/vnd.spire-io.channels+json;version=1.0", 
                "description": "application/vnd.spire-io.description+json;version=1.0", 
                "events": "application/vnd.spire-io.events+json;version=1.0", 
                "message": "application/vnd.spire-io.message+json;version=1.0", 
                "session": "application/vnd.spire-io.session+json;version=1.0", 
                "sessions": "application/vnd.spire-io.sessions+json;version=1.0", 
                "subscription": "application/vnd.spire-io.subscription+json;version=1.0", 
                "subscriptions": "application/vnd.spire-io.subscriptions+json;version=1.0"
                }
            }
        }
    }

NEW_SESSION = {
    "account": {
        "_channels": {}, 
        "channels": {
            "resources": {}, 
            "url": "http://localhost:3133/session/20/channels"
            }, 
        "key": 4, 
        "type": "account", 
        "url": "http://localhost:3133/session/4/account"
        }, 
    "channels": {
        "resources": {}, 
        "url": "http://localhost:3133/session/20/channels"
        }, 
    "subscriptions": {
        "url": "http://localhost:3133/session/20/subscriptions"
        }, 
    "type": "session", 
    "url": "http://localhost:3133/session/20"
    }

class TestSpireClient(unittest.TestCase):
    def setUp(self):
        self.client, self.server = self.get_client()
        if self.server is not None:
            self.server.run()

    def get_client(self):
        spire_key =  os.environ.get('SPIRE_KEY', None)
        if spire_key is not None:
            server = None
            client = spire.Client(
                os.environ.get('SPIRE_HOST', 'https://api.spire.io'),
                key = spire_key,
                async=False,
                )
        else:
            stub_port = 3133
            server = stubserver.StubServer(stub_port)
            client = spire.Client(
                "http://localhost/%i" % stub_port,
                async=False,
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

        messages = second_client_channel.subscribe(last_message_timestamp=0)
        eq(
            [x['content'] for x in messages][:2],
            ['with tangerine trees and marmalade skies', 'picture yourself on a boat on a river'],
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

    def test_last_message_parameter(self):
        raise SkipTest

    def test_delete_channel(self):
        raise SkipTest
