import os
import spire

import requests

def main():
    key = os.environ.get('SPIRE_KEY', None)
    host = os.environ.get('SPIRE_HOST', "http://localhost:1337")
    client = spire.Client(base_url=host, async=True, key=key)
    if not key:
        client.create_account('alice@example.com', 'password')

    session = client.session()

    #channels
    channel = session.channel()
    channel.publish('mr watson. come here. i need you.')

    #named channels
    named_channel = session.channel('foo', 'the foo channel')
    named_channel.publish('What hath Shark wrought?')

    def get_callback(channel_name):
        def _callback(messages):
            print channel_name
            print "============="
            print messages
        return _callback

    channel.subscribe(callback=get_callback("Global channel"))
    named_channel.subscribe(callback=get_callback("Named channel"))
    
if __name__ == '__main__':
    main()
