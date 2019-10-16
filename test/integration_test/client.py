import os
import time
from threading import Thread
from caraml.zmq import *


def handler(msg):
  print('handling', msg)
  msg['counter'] += 1
  msg['scream'] += 'a'
  return msg


class Server:

  def __init__(self):
    client = ZmqClient(host=os.environ['SYMPH_TEST_HOST'],
                       port=os.environ['SYMPH_TEST_PORT'],
                       serializer='pickle',
                       deserializer='pickle')
    client.start_loop(blocking=False)

    msg = {'counter': 10, 'scream': 'hello'}

    for _ in range(20):
      time.sleep(.1)
      msg = client.request(msg)


def main():
  cli = Client()


if __name__ == '__main__':
  main()
