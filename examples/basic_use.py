import spire

import requests

import sys
requests.settings.verbose = sys.stderr

def main():
    client = spire.Client('http://localhost:1337', async=False)
    client.create_account('alice@example.com', 'password')

    session = client.session()
    #channels
    channel = session.channel()
    channel.publish('mr watson. come here. i need you.')

    #named channels
    named_channel = session.channel('foo', 'the foo channel')
    named_channel.publish('What hath Shark wrought?')

    #subchannels
    subchannel = named_channel.subchannel('bar')
    subchannel.publish('Can you hear me now?')

    print "Global channel:"
    print "============="
    print channel.subscribe()

    print "Named channel:"
    print "============="
    print named_channel.subscribe()


    print "Subchannel:"
    print "============="
    print subchannel.subscribe()
    
if __name__ == '__main__':
    main()
