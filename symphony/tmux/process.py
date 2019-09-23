import os
from symphony.spec import ProcessSpec
from symphony.utils.common import print_err
from .common import tmux_name_check


class TmuxProcessSpec(ProcessSpec):

  def __init__(self,
               name,
               node,
               cmds=None,
               start_dir=None,
               preferred_ports=[],
               port_range=None):
    """
        Args:
            name: name of the process
            cmds: list of commands to run
            start_dir: directory in which the process starts
            node: Host machine for the process.
                  This is used to poll for avail. ports and add ssh commands.
        """
    tmux_name_check(name, 'Process')
    super().__init__(name)

    if port_range is None:
      port_range = range(6000, 20000)

    self.preferred_ports = preferred_ports
    self.port_range = list(preferred_ports) + list(port_range)
    self.node = node
    if cmds is None:
      cmds = []
    self.start_dir = os.path.expanduser(start_dir or '.')
    if not isinstance(cmds, (tuple, list)):
      print_err('[Warning] command "{}" for TmuxProcess "{}" should be a list'.
                format(cmds, name))
      self.cmds = [cmds]
    else:
      self.cmds = list(cmds)
    self.env = {}

  def get_port(self, port=None):
    exclude_ports = set(self.node.get_unavailable_ports())

    if port:  # requesting port
      if port in exclude_ports:
        raise Exception('Requesting %d port which is already taken!' % port)
      if port in self.port_range:
        self.port_range.remove(port)
        self.node.reserve_port(port)
      return port
    else:
      for port in self.port_range[:]:
        if port not in exclude_ports:
          self.port_range.remove(port)
          self.node.reserve_port(port)
          return port

      raise Exception('Run out of ports to allocate')

  @property
  def ip_addr(self):
    return self.node.ip_addr

  @property
  def shell_setup_commands(self):
    cmds = self.node.get_shell_setup_cmds()
    assert isinstance(cmds, list)
    return cmds

  @property
  def ssh_commands(self):
    cmd = self.node.get_ssh_cmd()
    if cmd:
      return [cmd]
    else:
      return []

  def set_envs(self, di):
    """
        Set environment variables
        Args:
            di(env_var_name(str): env_var_val(str))
        """
    for k, v in di.items():
      self.env[k] = str(v)

  def _load_dict(self, di):
    super()._load_dict(di)
    self.start_dir = di['start_dir']
    self.cmds = di['cmds']

  def dump_dict(self):
    di = super().dump_dict()
    di['start_dir'] = self.start_dir
    di['cmds'] = self.cmds
    return di
