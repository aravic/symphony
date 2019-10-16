import os
import argparse
import time
from threading import Thread
from caraml.zmq import *

parser = argparse.ArgumentParser()
parser.add_argument('--timeout', type=int, default=100)
args = parser.parse_args()


def handler(msg):
  print('handling', msg)
  msg['counter'] += 1
  msg['scream'] += 'a'
  return msg


class Server:

  def __init__(self):
    self.server = ZmqServer(host='127.0.0.1',
                            port=os.environ['SYMPH_TEST_PORT'],
                            serializer='pickle',
                            deserializer='pickle')
    self.server.start_loop(blocking=False)
    self._thread = Thread(target=self.server.start_loop, args=[handler])
    self._thread.daemon = True
    self._thread.start()


def main():
  s = Server()
  print('Timed out...')
  time.sleep(args.timeout)


if __name__ == '__main__':
  main()
