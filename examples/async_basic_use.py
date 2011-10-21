import spire

import requests

def main():
    client = spire.Client('http://localhost:1337', async=True)
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

    def get_callback(channel_name):
        def _callback(messages):
            print channel_name
            print "============="
            print messages
        return _callback

    channel.subscribe(callback=get_callback("Global channel"))
    named_channel.subscribe(callback=get_callback("Named channel"))
    subchannel.subscribe(callback=get_callback("Subchannel"))
    
if __name__ == '__main__':
    main()
