import argparse
import time

from easy_dict import EasyDict as ConfigDict
from symphony.commandline import SymphonyParser
from symphony.engine import Cluster
from symphony.tmux import Node

parser = argparse.ArgumentParser()
parser.add_argument('--mode',
                    type=str,
                    required=True,
                    help='Options: localhost, ssh, slurm')

ENV_ACTIVATE_CMD = 'conda activate symphony'
PYTHONPATH_CMD = 'export PYTHONPATH="$PYTHONPATH:`pwd`"'
PREAMBLE_CMDS = [ENV_ACTIVATE_CMD, PYTHONPATH_CMD]
EXP_NAME = 'SYMPH_INTEGRATION_TESTdfj4515'


def create_program(exp):
  serv = exp.new_process('server')
  cli = exp.new_process('client')
  serv.binds('test')
  cli.connects('test')

  for proc in [serv, cli]:
    name = proc.name
    config = ConfigDict()
    config[name].cpu = 1
    config[name].mem = 0
    config[name].gpu_compute = []
    config[name].gpu_mem = []
    proc.set_costs(**config)

  return serv, cli


def localhost_setup():
  node = Node(
      'localhost',
      '127.0.0.1',
      os.path.dirname(os.path.abspath(__file__)),
  )
  return node


def localhost_placement(serv, cli, node):
  serv.set_placement(node)
  cl.set_placement(node)


def main(argv):
  args = parser.parse_args(argv[1:])

  cluster = Cluster.new('tmux')

  exp = cluster.new_experiment(EXP_NAME, env_name='liaison')
  exp.set_preamble_cmds(PREAMBLE_CMDS)
  serv, cli = create_program(exp)

  if args.mode == 'localhost':
    node = localhost_setup()
    localhost_placement(serv, cli, node)
  else:
    raise Exception('Unknown mode %s' % args.mode)
  try:
    cluster.launch()
    time.sleep(100000)
  except KeyboardInterrupt:
    cluster.delete(experiment_name=EXP_NAME)


if __name__ == '__main__':
  app.run(main)
