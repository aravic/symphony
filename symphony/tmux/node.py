import logging
import os
import subprocess

import paramiko
from caraml.zmq import ZmqTimeoutError, get_remote_client
from spy import Server as SpyServer
from symphony.utils import ConfigDict


class Node:

  def __init__(self,
               name,
               ip_addr,
               base_dir,
               shell_setup_commands=[],
               use_ssh=True,
               ssh_key_file=None,
               ssh_port=22,
               ssh_username=None,
               ssh_config_file_path=None,
               spy_port=None,
               **kwargs):

    del kwargs
    self.name = name
    self._ip_addr = ip_addr
    self.ssh_key_file = ssh_key_file
    self.ssh_port = ssh_port
    self._ssh_client = None
    self._sftp_client = None
    self.ssh_username = ssh_username
    self._base_dir = base_dir
    self.spy_port = spy_port
    assert isinstance(shell_setup_commands, list)
    self.shell_setup_commands = ["cd '%s'" % base_dir
                                 ] + list(shell_setup_commands)
    self.use_ssh = use_ssh
    self.reserved_ports = []
    # If key file is not given, check
    # if default config option is viable
    if use_ssh and self.ssh_key_file is None:
      if ssh_config_file_path is None and ssh_username is not None:
        ssh_config_file_path = '/home/%s/.ssh/config' % ssh_username
      config = paramiko.SSHConfig()
      with open(ssh_config_file_path, 'r') as f:
        config.parse(f)

      res = config.lookup(ip_addr)
      if 'identityfile' in res:
        self.ssh_key_file = res['identityfile']
      else:
        raise Exception(
            'ssh key file not provided and default not found in ssh config file at %s'
            % ssh_config_file_path)

    self._capacity = None
    self._util = None
    self.collected_spy_stats = False

  def _get_ssh_client(self):
    if self._ssh_client:
      return self._ssh_client

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(self._ip_addr,
                   username=self.ssh_username,
                   port=self.ssh_port,
                   key_filename=self.ssh_key_file)
    client.get_transport().window_size = 2147483647
    self._ssh_client = client
    return self._ssh_client

  def _get_sftp_client(self):
    if self._sftp_client: return self._sftp_client
    self._sftp_client = self._get_ssh_client().open_sftp()
    return self._sftp_client

  def _ssh_run_cmd(self, ssh_client, cmd):
    _, out, err = ssh_client.exec_command(cmd)
    out = list(out)
    err = list(err)
    if err:
      raise Exception(
          'Exception encountered when executing command "{cmd}" on server {ip}:{port}: %s'
          .format(
              cmd=cmd,
              ip=self._ip_addr,
              port=self.ssh_port,
          ))
    return ''.join(out)

  def _local_run_cmd(self, cmd):
    result = subprocess.run(cmd.split(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.stderr:
      raise Exception(
          'exception encountered when executing command "{cmd}" locally'.
          format(cmd=cmd))
    if result.stdout is None:
      return ''
    else:
      return result.stdout.decode('utf-8')

  def _run_cmd(self, cmd):
    if self.use_ssh:
      ssh_cli = self._get_ssh_client()
      return self._ssh_run_cmd(ssh_cli, cmd)
    else:
      return self._local_run_cmd(cmd)

  def _put_dir(self, source, target):
    ''' Uploads the contents of the source directory to the target path. The
          target directory needs to exists. All subdirectories in source are
          created under target.
      '''
    for item in os.listdir(source):
      if os.path.isfile(os.path.join(source, item)):
        self._put(os.path.join(source, item), '%s/%s' % (target, item))
      else:
        self.mkdirs('%s/%s' % (target, item))
        self._put_dir(os.path.join(source, item), '%s/%s' % (target, item))

  def _put(self, src_fname, dst_fname):
    """Both paths should be full."""
    logging.info('Transferring file %s to %s', src_fname, self._ip_addr)
    sftp_cli = self._get_sftp_client()
    if sftp_cli is None:
      raise Exception('Not supported without ssh.')
    return sftp_cli.put(src_fname, dst_fname)

  # ========== PUBLIC API ================

  @property
  def ip_addr(self):
    return self._ip_addr

  @property
  def base_dir(self):
    return self._base_dir

  def get_shell_setup_cmds(self):
    return self.shell_setup_commands

  def get_unavailable_ports(self):
    # https://superuser.com/questions/529830/get-a-list-of-open-ports-in-linux
    out = self._run_cmd('ss -lnt')
    ports = list(self.reserved_ports)
    for x in out.split('\n')[1:]:  # read line by line skipping header
      l = x.split()  # split on whitespace.
      if len(l) > 3:  # Look for the 4th field.
        port = l[3].split(':')[-1]  # split :::3356 => 3356
        ports.append(int(port))
    return ports

  def get_ssh_cmd(self):
    if self.use_ssh:
      cmd = 'ssh -o StrictHostKeyChecking=no'
      if self.ssh_port:
        cmd += ' -p %d' % self.ssh_port
      if self.ssh_key_file:
        cmd += ' -i %s' % self.ssh_key_file
      cmd += ' %s@%s' % (self.ssh_username, self._ip_addr)
    else:
      cmd = ''
    return cmd

  def reserve_port(self, port):
    # no double commitment
    assert port not in self.reserved_ports
    self.reserved_ports.append(port)

  def put_file(self, src_fname, dst_fname):
    """dst_fname should be full path.
        Creates directories if required."""
    dst_fname = os.path.normpath(dst_fname)
    self.mkdirs(os.path.dirname(dst_fname))
    self._put(src_fname, dst_fname)

  def put_dir(self, src_path, dst_path):
    dst_path = os.path.normpath(dst_path)
    self.mkdirs(os.path.dirname(dst_path))
    self._put_dir(src_path, dst_path)

  def mkdirs(self, path):
    ''' Augments mkdir by adding an option to not fail if the folder exists  '''
    self._run_cmd("mkdir -p '%s'" % path)

  def collect_spy_stats(self, measurement_time):
    try:
      rc = get_remote_client(SpyServer,
                             host=self._ip_addr,
                             port=self.spy_port,
                             timeout=measurement_time + 5)
      self._capacity = ConfigDict(rc.get_capacity())
      self._util = ConfigDict(rc.get_instantaneous_profile(measurement_time))
      self._util.gpu_compute = []
      self._util.gpu_mem = []
      while True:
        i = 0
        broken = False
        for k in self._util:
          if 'gpu/%d' % i in k:
            self._util['gpu_compute'].append(self._util['gpu/%d/compute' % i])
            self._util['gpu_mem'].append(self._util['gpu/%d/memory' % i])
            broken = True
            break
        if not broken:
          break
        i += 1
      self.collected_spy_stats = True
    except ZmqTimeoutError as e:
      print('Unable to connect to SPY Server: %s:%d' %
            (self.ip_addr, self.spy_port))
      raise e

  def _check_spy_stats_available(self):
    if not self.collected_spy_stats:
      raise Exception('Collect spy stats before quering for available metrics')
    return True

  def avail_cpu(self):
    self._check_spy_stats_available()
    return self._util.cpu - self._capacity.cpu

  def avail_mem(self):
    self._check_spy_stats_available()
    return self._util.memory - self._capacity.memory

  def avail_gpu_compute(self, gpu_model_to_scale):
    """
      gpu_model_to_scale is a dict from model string to scale.
    """
    self._check_spy_stats_available()
    l = []
    for u, model in zip(self._util.gpu_compute, self._capacity.gpu_model):
      found = False
      for k, scale in gpu_model_to_scale.items():
        if k in model:
          found = True
          break

      if found:
        l.append(scale * (1 - u))
      else:
        raise Exception('Unknown GPU model %s found on host %s' %
                        (model, self.name))

    return l

  def avail_gpu_mem(self):
    self._check_spy_stats_available()
    return [c - u for c, u in zip(self._capacity.gpu_mem, self._util.gpu_mem)]
