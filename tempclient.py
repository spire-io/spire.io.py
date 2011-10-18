try:
    import json
except ImportError:
    import simplejson as json

from pprint import pprint

import spire

import requests

def main():
    client = spire.Client('http://localhost:1337', async=False)
    client._discover() # TODO: discovery will happen automatically
    client.create_account() # TODO: automate account creation if no key is passed?
    session = client.get_session()
    channel = session.channel()
    channel.publish('mr watson. come here. i need you.')
    pprint(channel.subscribe())
    
if __name__ == '__main__':
    main()
