from .base import BaseSpec
from symphony.utils.common import check_valid_dns


def parse_service_spec(spec):
  """
        Compiles port specification, it can be (tested in this order):
        (str): arrange an arbitrary port for this service
        (list(str)):arrange an arbitrary port for every string in the list
        (dict): for 'k','v' in dict: arrange port 'v' for service 'k'
    """
  if isinstance(spec, str):
    check_valid_dns(spec)
    return {spec: None}
  if isinstance(spec, list) or isinstance(spec, tuple):
    for name in spec:
      check_valid_dns(name)
    return {name: None for name in spec}
  if isinstance(spec, dict):
    for name in spec:
      check_valid_dns(name)
      if not isinstance(spec[name], int) and (spec[name] is not None):
        raise ValueError('[Error] Invalid port number {}, expected int'.format(
            spec[name]))
    return spec


class ProcessSpec(BaseSpec):

  def __init__(self, name):
    super().__init__(name)
    self.parent_process_group = None
    self.parent_experiment = None
    self.binded_services = {}
    self.connected_services = {}
    self.exposed_services = {}

  def _set_experiment(self, experiment):
    """ Internal method
            Set process to belong to experiment
        """
    if self.parent_experiment is not None:
      raise ValueError('[Error] Process {} cannot be added to experiment {}. \
                It is already in experiment {}'.format(
          self.name, experiment.name, self.parent_experiment.name))
    self.parent_experiment = experiment

  def _set_process_group(self, process_group):
    """ Internal method
            Set process to belong to process_group
        """
    if self.parent_process_group is not None:
      raise ValueError('[Error] Process {} cannot be added to process_group {}. ' \
          'It is already in process_group {}'.format(self.name,
                                                     process_group.name,
                                                     self.parent_process_group.name))
    self.parent_process_group = process_group

  # TODO: docs about bind/connect/expose input format
  def binds(self, spec):
    """ Declare that this process binds to an address / provides a service
        so others can connect to it
        Args:
        spec(str/list(str)/dict(str: int)): specify the services to provide
        """
    self.binded_services.update(parse_service_spec(spec))

  def connects(self, spec):
    """ Declare that this process connects to an address / an service
        Args:
        """
    spec = parse_service_spec(spec)
    for k in spec:
      if spec[k] is not None:
        raise ValueError(
            '[Error] When connecting to {}, a port is specified. Port must be None when connecting'
            .format(k))
    self.connected_services.update(spec)

  def exposes(self, spec):
    """ Declare that this process binds to an address / provides a service
            so user can connect to it externally, i.e. use `symphony visit <service_name>`
            Args:
        """
    self.exposed_services.update(parse_service_spec(spec))

  @classmethod
  def load_dict(cls, di):
    """
        For creating new instances
        """
    instance = cls(di['name'])
    instance._load_dict(di)
    return instance

  def _load_dict(self, data):
    """
        Loads information from data, can be inherited
        """
    self.binded_services = data['binded_services']
    self.connected_services = data['connected_services']
    self.exposed_services = data['exposed_services']

  def dump_dict(self):
    data = {'name': self.name}
    data['binded_services'] = self.binded_services
    data['connected_services'] = self.connected_services
    data['exposed_services'] = self.exposed_services
    return data
