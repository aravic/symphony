import os

from symphony.spec import ProcessSpec
from symphony.utils.common import print_err

from .common import tmux_name_check


class TmuxProcessSpec(ProcessSpec):

  def __init__(self,
               name,
               node=None,
               cmds=None,
               allocation=None,
               preferred_ports=[],
               port_range=None):
    """
        Args:
            name: name of the process
            cmds: list of commands to run
            node: Host machine for the process.
                  This is used to poll for avail. ports and add ssh commands.
        """
    tmux_name_check(name, 'Process')
    super().__init__(name)

    if port_range is None:
      port_range = range(6000, 20000)

    self.allocation = allocation
    self.preferred_ports = preferred_ports
    self.port_range = list(preferred_ports) + list(port_range)
    self.node = node
    if cmds is None:
      cmds = []
    if not isinstance(cmds, (tuple, list)):
      print_err('[Warning] command "{}" for TmuxProcess "{}" should be a list'.
                format(cmds, name))
      self.cmds = [cmds]
    else:
      self.cmds = list(cmds)
    # overwrite CUDA_VISIBLE_DEVICES with set_gpus
    self.env = dict(CUDA_VISIBLE_DEVICES='')
    self.cpu_cost = None
    self.mem_cost = None
    self.gpu_compute_cost = None
    self.gpu_mem_cost = None
    self.hard_placement = None

  def append_cmds(self, cmds):
    self.cmds.extend(cmds)

  def set_placement(self, node):
    self.node = node

  def set_allocation(self, allocation):
    self.allocation = allocation

  def set_gpus(self, gpus):
    self.env['CUDA_VISIBLE_DEVICES'] = ','.join(map(str, gpus))

  def get_port(self, port=None):
    allocation = self.allocation
    exclude_ports = set(self.node.get_unavailable_ports(allocation))

    if port:  # requesting port
      if port in exclude_ports:
        raise Exception('Requesting %d port which is already taken!' % port)
      if port in self.port_range:
        self.port_range.remove(port)
        self.node.reserve_port(port, allocation)
      return port
    else:
      for port in self.port_range[:]:
        if port not in exclude_ports:
          self.port_range.remove(port)
          self.node.reserve_port(port, allocation)
          return port

      raise Exception('Run out of ports to allocate')

  @property
  def ip_addr(self):
    if self.node is None:
      raise Exception('Node not set in process %s' % self.name)
    return self.node.get_ip_addr(allocation=self.allocation)

  def get_tmux_cmd(self, preamble_cmds):
    login_cmds = self.node.get_login_cmds()
    l = self.node.get_allocation_cleanup_cmds(self.allocation)
    cleanup_cmds = []
    if l:
      cleanup_cmds = [
          'signal_handler() { %s ; }; trap signal_handler HUP TERM EXIT' %
          ';'.join(l)
      ]

    app_cmds = self.node.dry_run(*(preamble_cmds + self.cmds),
                                 allocation=self.allocation)
    return login_cmds + cleanup_cmds + app_cmds

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
    self.cmds = di['cmds']

  def dump_dict(self):
    di = super().dump_dict()
    di['cmds'] = self.cmds
    return di

  def set_costs(self, cpu, mem, gpu_compute, gpu_mem):
    self.cpu_cost = float(cpu)
    self.mem_cost = float(mem)
    self.gpu_compute_cost = list(map(float, gpu_compute))
    self.gpu_mem_cost = list(map(float, gpu_mem))

  def set_hard_placement(self, node_name):
    self.hard_placement = node_name
