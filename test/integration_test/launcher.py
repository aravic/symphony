"""python -m test.integration_test.launcher --pdb_post_mortem -- --mode=localhost"""
import argparse
import os
import time

from absl import app
from ccc.src.local_node import Node as LocalNode
from ccc.src.load_nodes import NodeLoader
from easydict import EasyDict as ConfigDict
from symphony.commandline import SymphonyParser
from symphony.engine import Cluster
import argon

parser = argon.ArgumentParser()
parser.add_config_file(name='cluster', default='../ccc/ccc/config.py')
subparsers = parser.add_subparsers(dest='command')
mode_parser = subparsers.add_parser('mode')
mode_parser.add_argument('mode',
                         type=str,
                         help='Options: localhost, ssh, slurm')
mode_parser.add_argument('--filter_regex', type=str, default='.*')

ENV_ACTIVATE_CMD = 'conda activate liaison'
PYTHONPATH_CMD = 'export PYTHONPATH="$PYTHONPATH:`pwd`"'
PREAMBLE_CMDS = [ENV_ACTIVATE_CMD, PYTHONPATH_CMD]
EXP_NAME = 'SYMPH_INTEGRATION_TEST'

FILE_DIR = os.path.dirname(os.path.realpath(__file__))
RES_FILES = [os.path.join(FILE_DIR, s) for s in ('server.py', 'client.py')]


def create_program(exp):
  serv = exp.new_process('server')
  cli = exp.new_process('client')
  serv.binds('test')
  cli.connects('test')

  for proc in [serv, cli]:
    name = proc.name
    config = ConfigDict()
    config.cpu = 1
    config.mem = 0
    config.gpu_compute = []
    config.gpu_mem = []
    proc.set_costs(**config)

  serv.append_cmds(['python server.py'])
  cli.append_cmds(['python client.py'])
  return serv, cli


def localhost_setup():
  node = LocalNode(
      'localhost',
      '127.0.0.1',
      '/home/ubuntu/ccc/src/',
      shell_setup_commands=[
          'source /home/ubuntu/ccc/env/anaconda3/etc/profile.d/conda.sh'
      ])
  node.setup(res_files=RES_FILES)
  return node


def localhost_placement(serv, cli, node):
  serv.set_placement(node)
  cli.set_placement(node)


def ssh_placement(serv, cli, local_node, ssh_node):
  serv.set_placement(ssh_node)
  cli.set_placement(local_node)


def slurm_placement(serv, cli, local_node, slurm_node):
  serv.set_placement(slurm_node)
  allocation = slurm_node.allocate(cpu=1, mem=1024, n_gpus=1)
  serv.set_allocation(allocation)
  cli.set_placement(local_node)


def main(argv):
  args = parser.parse_args(argv[1:])
  assert args.command == 'mode'

  cluster = Cluster.new('tmux')
  exp = cluster.new_experiment(EXP_NAME)
  exp.set_preamble_cmds(PREAMBLE_CMDS)
  serv, cli = create_program(exp)

  if args.mode == 'localhost':
    node = localhost_setup()
    localhost_placement(serv, cli, node)
  elif args.mode == 'ssh':
    nodeloader = NodeLoader(
        ConfigDict(argon.to_nested_dicts(args.cluster_config)),
        args.filter_regex)
    nodes = nodeloader.nodes
    if len(nodes) != 1:
      raise Exception(
          'For this test condition, please specify just a single ssh node.')
    ssh_node = nodes[0]
    ssh_node.setup(res_files=RES_FILES)
    local_node = localhost_setup()
    ssh_placement(serv, cli, local_node, ssh_node)
  elif args.mode == 'slurm':
    nodeloader = NodeLoader(
        ConfigDict(argon.to_nested_dicts(args.cluster_config)),
        args.filter_regex)
    nodes = nodeloader.nodes
    if len(nodes) != 1:
      raise Exception(
          'For this test condition, please specify just a single slurm node.')
    slurm_node = nodes[0]
    slurm_node.setup(res_files=RES_FILES)
    local_node = localhost_setup()
    slurm_placement(serv, cli, local_node, slurm_node)
  else:
    raise Exception('Unknown mode %s' % args.mode)

  try:
    cluster.launch(exp)
    while True:
      time.sleep(100000)
  except KeyboardInterrupt:
    cluster.delete(experiment_name=EXP_NAME)


if __name__ == '__main__':
  app.run(main)
