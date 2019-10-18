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
    self.server = ZmqServer(host='*',
                            port=os.environ['SYMPH_TEST_PORT'],
                            serializer='pickle',
                            deserializer='pickle')
    self._thread = Thread(target=self.server.start_loop,
                          args=[handler],
                          kwargs=dict(blocking=True))
    self._thread.daemon = True
    self._thread.start()


def main():
  s = Server()
  time.sleep(args.timeout)
  print('Timed out...')


if __name__ == '__main__':
  main()
