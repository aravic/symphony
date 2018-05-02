from .base import BaseSpec
from .process import ProcessSpec
from .process_group import ProcessGroupSpec
from symphony.engine.application_config import SymphonyConfig
# from symphony.utils.common import 


class ExperimentSpec(BaseSpec):
    def __init__(self, name):
        if SymphonyConfig().prefix_username and SymphonyConfig().username:
            if name.find(SymphonyConfig().username) != 0:
                name = SymphonyConfig().username + '-' + name
        super().__init__(name)
        self.lone_processes = {}
        self.all_processes = {}
        self.process_groups = {}
        
    def add_process_group(self, process_group):
        assert isinstance(process_group, ProcessGroupSpec)
        process_group_name = process_group.name
        if process_group_name in self.process_groups:
            raise ValueError('[Error] Cannot add process group {} to experiment \
                {}: a process group with the same name already exists'.format(process_group_name, self.name))
        self.process_groups[process_group_name] = process_group
        process_group._set_experiment(self)

    def add_process_groups(self, process_groups):
        for pg in process_groups:
            self.add_process_group(pg)

    def new_process_group(self, *args, **kwargs):
        """
        Call self.add_process_group

        Returns:
            new ProcessGroupSpec
        """
        pg = self._new_process_group(*args, **kwargs)
        self.add_process_group(pg)
        return pg

    def _new_process_group(self, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def _process_group_class(cls):
        """
        Returns ProcessGroupSpec
        """
        raise NotImplementedError

    def get_process_group(self, name):
        return self.process_groups[name]

    def list_process_groups(self):
        return self.process_groups.values()

    def add_process(self, process, lone=True):
        assert isinstance(process, ProcessSpec)
        process_name = process.name
        if process_name in self.all_processes:
            raise ValueError('[Error] Cannot add process {} to experiment \
            {}: a process with the same name already exists'.format(process_name, self.name))
        if lone:
            self.lone_processes[process_name] = process
        self.all_processes[process_name] = process
        process._set_experiment(self)

    def add_processes(self, processes):
        for p in processes:
            self.add_process(p)

    def new_process(self, *args, **kwargs):
        """
        Returns:
            new ProcessSpec
        """
        p = self._new_process(*args, **kwargs)
        self.add_process(p)
        return p

    def _new_process(self, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def _process_class(cls):
        """
        Returns ProcessSpec
        """
        raise NotImplementedError

    def get_process(self, name):
        return self.lone_processes[name]

    def list_lone_processes(self):
        return self.lone_processes.values()

    def list_all_processes(self):
        return self.all_processes.values()

    @classmethod
    def load_dict(cls, di):
        name = di['name']
        instance = cls(name)
        instance._load_dict(di)
        return instance

    def _load_dict(self, di):
        pgs = di['process_groups']
        for dictionary in pgs:
            self.add_process_group(self._process_group_class().load_dict(dictionary))
        ps = di['processes']
        for dictionary in ps:
            self.add_process(self._process_class().load_dict(dictionary))

    def dump_dict(self):
        pgs = []
        for process_group in self.list_process_groups():
            pgs.append(process_group.dump_dict())
        ps = []
        for process in self.list_processes():
            ps.append(process.dump_dict())
        return {'process_groups': pgs, 'processes': ps, 'name': self.name}
