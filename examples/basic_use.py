import spire

import requests

def main():
    client = spire.Client('http://localhost:1337', async=False)
    client.create_account() # TODO: automate account creation if no key is passed?
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
    print [x['message'] for x in channel.subscribe()['messages']]

    print "Named channel:"
    print "============="
    print [x['message'] for x in named_channel.subscribe()['messages']]

    print "Subchannel:"
    print "============="
    print [x['message'] for x in subchannel.subscribe()['messages']]
    
if __name__ == '__main__':
    main()