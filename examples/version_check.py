"""
Example application using spire library for realtime notifications
"""
import optparse
import signal
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

def run(client, node, dots=True):
    channel = client.session().channel('myService.versionNotifier')
    while True:
        messages = channel.subscribe()
        if dots:
            sys.stdout.write('.')
            sys.stdout.flush()
        # TODO filter support
        for message in messages:
            if message['message'].startswith('report:'):
                sys.stdout.write(message['message'] + '\n')
                sys.stdout.flush()

        if 'getVersion' in [x['message'] for x in messages]:
            channel.publish('report: %s: %s' % (node, report_version()))
        time.sleep(2) # stubby doesn't long-poll

def ask(client):
    sys.stdout.write('asking\n')
    client.session().channel('myService.versionNotifier').publish('getVersion')
    
if __name__ == '__main__':
    parser = optparse.OptionParser(usage="%prog host key nodename")
    parser.add_option('--dots', action="store_true", default=False, dest="dots")
    opts, args = parser.parse_args()
    if len(args) != 3:
        parser.error('Host, key and nodename required')

    client = spire.Client(args[0], key=args[1], async=False) # Async mode NYI    
    def ask_handler(signum, stack):
        sys.stdout.write('asking in handler\n')
        ask(client)

    signal.signal(signal.SIGUSR1, ask_handler)
    run(client, args[2], opts.dots)
    

