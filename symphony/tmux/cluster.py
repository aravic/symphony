import os
import shlex
import time
from threading import Thread

import libtmux
from libtmux.exc import LibTmuxException
from symphony.engine import Cluster
from symphony.errors import *
from symphony.tmux.experiment import TmuxExperimentSpec

_DEFAULT_WINDOW = '__main__'


def _logger(verbose):

  def _log(*args, **kwargs):
    if verbose:
      print(*args, **kwargs)

  return _log


class TmuxCluster(Cluster):

  def __init__(self, server_name='default'):
    """
        Args:
            server_name: name of the new Tmux server (i.e. socket_name)
        """
    super().__init__()  # just for linter's happiness
    self._socket_name = server_name
    self._tmux = libtmux.Server(socket_name=self._socket_name,
                                config_file='/home/ubuntu/.tmux.conf')

  # =================== Private helpers ====================
  def _get_session(self, session_name):
    try:
      sess = self._tmux.find_where({'session_name': session_name})
    except LibTmuxException:
      raise ValueError('Experiment "{}" does not exist'.format(session_name))
    if not sess:
      raise ValueError('Experiment "{}" does not exist'.format(session_name))
    return sess

  def _get_window_name(self, process_name, group_name):
    if group_name:
      window_name = ':'.join((group_name, process_name))
    else:
      window_name = process_name
    return window_name

  def _get_window(self, session_name, process_name, group_name=None):
    sess = self._get_session(session_name)
    window_name = self._get_window_name(process_name, group_name)
    window = sess.find_where({'window_name': window_name})
    if not window:
      raise ValueError('Process "{}" does not exist'.format(window_name))
    return window

  def _new_session(self, session_name):
    try:
      if self._tmux.has_session(session_name):
        raise ResourceExistsError(
            'Experiment "{}" already exists'.format(session_name))
    except LibTmuxException:
      pass
    return self._tmux.new_session(session_name)

  def _create_process(self, sess, process, pane, preamble_cmds, timeout=4):
    # Retry loop to make sure we run process commands after
    # shell starts (heuristically checked by ensuring pane has
    # some output in the buffer).
    env_cmds = [
        'export {}={}'.format(k, shlex.quote(v))
        for k, v in process.env.items()
    ]
    cmds = process.get_tmux_cmd(env_cmds + preamble_cmds)
    if cmds:
      start_time = time.time()
      # while time.time() < start_time + timeout:
      while True:
        stdout = pane.cmd('capture-pane', '-p').stdout
        if stdout:
          for i, cmd in enumerate(cmds):
            pane.send_keys(cmd, suppress_history=False)
          break
        else:
          time.sleep(.5)

  def _new_window(self, sess, window_name):
    win = sess.new_window(window_name)
    win.select_layout('tiled')
    win.set_window_option('aggressive-resize', 'on')
    return win

  def _split_window(self, win):
    win.split_window(vertical=False)
    win.select_layout('tiled')
    win.set_window_option('aggressive-resize', 'on')
    return win

  # ===================== Launch API =======================
  def new_experiment(self, *args, **kwargs):
    return TmuxExperimentSpec(*args, **kwargs)

  def launch(self, spec, dry_run=False, verbose=True):
    _log = _logger(verbose)
    assert isinstance(spec, TmuxExperimentSpec)

    spec.compile()

    # Create a new session for the given Experiment.
    if not dry_run:
      sess = self._new_session(spec.name)
      # Change the name of the default window.
      sess.windows[0].rename_window(_DEFAULT_WINDOW)
    _log('Creating new Experiment "{}"'.format(spec.name))

    threads = []
    # Create a window for each process group and lone process.
    for pg in spec.list_process_groups():
      preamble_cmds = spec.preamble_cmds + pg.preamble_cmds
      _log(' --> Creating process group', pg.name)
      if not dry_run:
        # Create new window.
        pg_win = self._new_window(sess, window_name=pg.name)

      for i, p in enumerate(pg.list_processes()):
        is_last = (i == len(pg.list_processes()) - 1)
        if not dry_run:
          # self._create_process(self, p, pg_win.attached_pane, preamble_cmds)
          t = Thread(target=self._create_process,
                     args=(sess, p, pg_win.attached_pane, preamble_cmds))
          t.start()
          threads.append(t)
          if is_last:
            pass
          else:
            pg_win = self._split_window(pg_win)

        _log(' --> --> Created process', ':'.join((pg.name, p.name)))

    for p in spec.list_processes():
      if not dry_run:
        # Create new window.
        pane = self._new_window(sess, window_name=p.name).attached_pane
        # self._create_process(self, p, pane, spec.preamble_cmds)
        t = Thread(target=self._create_process,
                   args=(sess, p, pane, spec.preamble_cmds))
        t.start()
        threads.append(t)
      _log(' --> Created process', p.name)

    for thread in threads:
      thread.join()

  def launch_batch(self, experiment_specs):
    for exp in experiment_specs:
      self.launch(exp)

  # ===================== Action API =======================
  def delete(self, experiment_name):
    """Threadsafe if libtmux is thread-safe."""
    if experiment_name is None:
      experiment_name = self.current_experiment()
    sess = self._get_session(experiment_name)
    for win in sess.list_windows():
      for pane in win.list_panes():
        # send sigquit
        pane.send_keys('C-c', enter=False, suppress_history=False)
        # TODO: Add sigquit as well for cases where cmd won't quit
        # on interrupt.
    time.sleep(.1)
    sess.kill_session()

  def delete_batch(self, experiments):
    for exp in experiments:
      self.delete(exp)

  def transfer_file(self, experiment_name, src, dest):
    """
        scp for remote backends
        """
    # TODO
    raise NotImplementedError

  def login(self, experiment_name, *args, **kwargs):
    """
        ssh for remote backends
        """
    # TODO
    # tmux -L <server> select-window -t <session>:<window>; a -t <session>
    raise NotImplementedError

  def exec_command(self, experiment_name, command, *args, **kwargs):
    """
        command(array(string))
        """
    # XXX
    raise NotImplementedError

  # ===================== Query API ========================
  def set_experiment(self, experiment_name):
    """
        Args:
            experiment_name(str): to be set to default
        """
    print('Tmux cluster does not persist current experiments.')
    exit(0)

  def current_experiment(self):
    experiments = self.list_experiments()
    if len(experiments) == 0:
      print('No active experiments')
      exit(0)
    elif len(experiments) == 1:
      return experiments[0]
    else:
      print(
          'More than one experiments are active, please specify the experiment that you are querying for'
      )
      print('Active experiments:')
      for experiment in experiments:
        print('\t{}'.format(experiment))
      exit(0)

  def list_experiments(self):
    """
        Returns:
            list of experiment names
        """
    try:
      return [sess.name for sess in self._tmux.sessions]
    except LibTmuxException:
      return []

  def fuzzy_match_experiments(self):
    # TODO
    pass

  def describe_experiment(self, experiment_name):
    """
        Returns:
        {
            'pgroup1': {
                'p1': {'status': 'live', 'timestamp': '11:23'},
                'p2': {'status': 'dead'}
            },
            None: {  # always have all the processes
                'p3_lone': {'status': 'running'}
            }
        }
        """
    if experiment_name is None:
      experiment_name = self.current_experiment()
    sess = self._get_session(experiment_name)
    result = dict()
    for window in sess.windows:
      if window.name == _DEFAULT_WINDOW:
        continue
      tokens = window.name.split(':')
      if len(tokens) == 1:
        group, process = None, tokens[0]
      else:
        group, process = tokens[0], tokens[1]
      result[group] = result.get(group, dict())
      # TODO: Add other attributes available from tmux
      result[group][process] = {
          'status': 'live',
      }
    return result

  def describe_process_group(self, experiment_name, process_group_name):
    """
        Returns:
        {
            'p1': {'status': 'live', 'timestamp': '11:23'},
            'p2': {'status': 'dead'}
        }
        """
    return self.describe_experiment(experiment_name)[process_group_name]

  def describe_process(self,
                       experiment_name,
                       process_name,
                       process_group_name=None):
    """
        Returns:
            {'status: 'live', 'timestamp': '23:34'}
        """
    if experiment_name is None:
      experiment_name = self.current_experiment()
    window = self._get_window(experiment_name,
                              process_name,
                              group_name=process_group_name)
    # TODO: Add other attributes available from tmux
    return {
        'status': 'live',
    }

  def get_log(self,
              experiment_name,
              process_name,
              process_group=None,
              follow=False,
              since=None,
              tail=None,
              print_logs=False):
    # if follow:
    # raise Warning(
    # '[Warning] "follow" is not supported for tmux backend')
    # if since:
    # raise Warning(
    # '[Warning] "since" is not supported for tmux backend')
    if experiment_name is None:
      experiment_name = self.current_experiment()
    window = self._get_window(experiment_name,
                              process_name,
                              group_name=process_group)
    pane = window.attached_pane
    command = ['capture-pane', '-p']
    if tail:
      command.extend(['-S', str(-abs(tail))])
    stdout = pane.cmd(*command).stdout
    if print_logs:
      print('\n'.join(stdout))
    return stdout
