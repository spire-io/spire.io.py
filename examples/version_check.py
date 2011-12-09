"""
Example application using spire library for realtime notifications
"""
import optparse
import socket
import subprocess
import sys
import time

import spire

def report_version():
    return subprocess.Popen(
        'git rev-parse HEAD',
        shell=True,
        stdout=subprocess.PIPE,
        ).stdout.read()

def run(client, node, dots=True, last_message_timestamp=None):
    channel = client.session().channel('myService.versionNotifier')
    # set last message
    # oh python you crazy
    class MessageProcessor(object):
        def __init__(self, last_message_timestamp):
            if last_message_timestamp is None:
                last_message_timestamp = 0
            self.last_message_timestamp = last_message_timestamp
        def process(self, messages):
            for message in messages:
                last_message_timestamp = message['timestamp']
                if last_message_timestamp > self.last_message_timestamp:
                    self.last_message_timestamp = last_message_timestamp
                if message['content'].startswith('report:'):
                    sys.stdout.write(message['content'] + '\n')
                    sys.stdout.flush()
            fp = file('.last-message', 'w')
            fp.write(str(last_message_timestamp))
            fp.close()

            if 'getVersion' in [x['content'] for x in messages]:
                print "getting version"
                channel.publish('report: %s: %s' % (node, report_version()))
    mp = MessageProcessor(last_message_timestamp)
    while True:
        messages = channel.subscribe(
            last_message_timestamp=mp.last_message_timestamp,
            callback=mp.process,
            )
        if messages:
            mp.process(messages)
        if dots:
            sys.stdout.write('.')
            sys.stdout.flush()
        # TODO filter support


def ask(client):
    sys.stdout.write('asking\n')
    client.session().channel('myService.versionNotifier').publish('getVersion')
    
if __name__ == '__main__':
    last_message_timestamp = None
    try:
        fp = file('.last-message')
        last_message_timestamp = long(fp.read().strip())
        fp.close()
    except IOError:
        pass
    parser = optparse.OptionParser(usage="%prog wait|ask host key [nodename]")
    parser.add_option('--dots', action="store_true", default=False, dest="dots")
    opts, args = parser.parse_args()
    if len(args) < 3:
        parser.error('mode, host and key required')
    try:
        nodename = args[3]
    except IndexError:
        nodename = socket.gethostname()
    client = spire.Client(args[1], key=args[2], async=True)

    if args[0] == 'wait':
        run(client, nodename, opts.dots, last_message_timestamp)
    elif args[0] == 'ask':
        ask(client)
    else:
        parser.print_usage()
        sys.exit(1)
    

