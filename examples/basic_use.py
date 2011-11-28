import os
import sys

import spire

import requests

def main():
    key = os.environ.get('SPIRE_KEY', None)
    client = spire.Client(base_url="http://localhost:1337", async=False, key=key)
    if not key:
        client.create_account('alice@example.com', 'password')

    session = client.session()

    #channels
    channel = session.channel()
    channel.publish('mr watson. come here. i need you.')

    #named channels
    named_channel = session.channel('foo', 'the foo channel')
    named_channel.publish('What hath Shark wrought?')

    print "Default channel:"
    print "================"
    print channel.subscribe()

    print "Named channel:"
    print "============="
    print named_channel.subscribe()
    
if __name__ == '__main__':
    main()
