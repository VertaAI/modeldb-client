import re
import ast
import time

import requests
import joblib

from ._protos.public.modeldb import CommonService_pb2 as _CommonService
from ._protos.public.modeldb import ProjectService_pb2 as _ProjectService
from ._protos.public.modeldb import ExperimentService_pb2 as _ExperimentService
from ._protos.public.modeldb import ExperimentRunService_pb2 as _ExperimentRunService
from . import _utils


class ModelDBClient:
    """
    Object for interfacing with the ModelDB backend.

    This class provides functionality for starting/resuming Projects, Experiments, and Experiment
    Runs.

    Parameters
    ----------
    host : str, default "localhost"
        Hostname of the node running the ModelDB backend.
    port : str or int, default "8080"
        Port number to which the ModelDB backend is listening.
    email : str or None, default None
        Authentication credentials for managed service. If this does not sound familiar, then there
        is no need to set it.
    dev_key : str or None, default None
        Authentication credentials for managed service. If this does not sound familiar, then there
        is no need to set it.

    Attributes
    ----------
    proj : :class:`Project` or None
        Currently active Project.
    expt : :class:`Experiment` or None
        Currently active Experiment.
    expt_runs : :class:`ExperimentRuns` or None
        ExperimentRuns under the currently active Experiment.

    """
    _GRPC_PREFIX = "Grpc-Metadata-"

    def __init__(self, host="localhost", port="8080", email=None, dev_key=None):
        if email is None and dev_key is None:
            self._auth = None
        elif email is not None and dev_key is not None:
            self._auth = {self._GRPC_PREFIX+'email': email,
                          self._GRPC_PREFIX+'developer_key': dev_key,
                          self._GRPC_PREFIX+'source': "PythonClient"}
        else:
            raise ValueError("`email` and `dev_key` must be provided together")

        self._socket = "{}:{}".format(host, port)

        self.proj = None
        self.expt = None

    @property
    def expt_runs(self):
        if self.expt is None:
            return None
        else:
            Message = _ExperimentRunService.GetExperimentRunsInProject
            msg = Message(project_id=self.proj._id)
            data = _utils.proto_to_json(msg)
            response = requests.get("http://{}/v1/experiment-run/getExperimentRunsInProject".format(self._socket),
                                    params=data, headers=self._auth)
            if response.ok:
                response_msg = _utils.json_to_proto(response.json(), Message.Response)
                expt_run_ids = [expt_run.id
                                for expt_run in response_msg.experiment_runs
                                if expt_run.experiment_id == self.expt._id]
                return ExperimentRuns(self._auth, self._socket, expt_run_ids)
            else:
                raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def set_project(self, proj_name=None, desc=None, tags=None, attrs=None):
        """
        Attaches a Project to this Client.

        If an accessible Project with name `proj_name` does not already exist, it will be created
        and initialized with specified metadata parameters. If such a Project does  already exist,
        it will be retrieved; specifying metadata parameters in this case will raise an exception.

        If an Experiment is already attached to this Client, it will be detached.

        Parameters
        ----------
        proj_name : str, optional
            Name of the Project. If no name is provided, one will be generated.
        desc : str, optional
            Description of the Project.
        tags : list of str, optional
            Tags of the Project.
        attrs : dict of str to {None, bool, float, int, str}, optional
            Attributes of the Project.

        Returns
        -------
        :class:`Project`

        Raises
        ------
        ValueError
            If a Project with `proj_name` already exists, but metadata parameters are passed in.

        """
        # if proj already in progress, reset expt
        if self.proj is not None:
            self.expt = None

        proj = Project(self._auth, self._socket,
                       proj_name,
                       desc, tags, attrs)

        self.proj = proj
        return proj

    def set_experiment(self, expt_name=None, desc=None, tags=None, attrs=None):
        """
        Attaches an Experiment under the currently active Project to this Client.

        If an accessible Experiment with name `expt_name` does not already exist under the currently
        active Project, it will be created and initialized with specified metadata parameters. If
        such an Experiment does already exist, it will be retrieved; specifying metadata parameters
        in this case will raise an exception.

        Parameters
        ----------
        expt_name : str, optional
            Name of the Experiment. If no name is provided, one will be generated.
        desc : str, optional
            Description of the Experiment.
        tags : list of str, optional
            Tags of the Experiment.
        attrs : dict of str to {None, bool, float, int, str}, optional
            Attributes of the Experiment.

        Returns
        -------
        :class:`Experiment`

        Raises
        ------
        ValueError
            If an Experiment with `expt_name` already exists, but metadata parameters are passed in.
        AttributeError
            If a Project is not yet in progress.

        """
        if self.proj is None:
            raise AttributeError("a project must first in progress")

        expt = Experiment(self._auth, self._socket,
                          self.proj._id, expt_name,
                          desc, tags, attrs)

        self.expt = expt
        return expt

    def set_experiment_run(self, expt_run_name=None, desc=None, tags=None, attrs=None):
        """
        Attaches an Experiment Run under the currently active Experiment to this Client.

        If an accessible Experiment Run with name `expt_run_name` does not already exist under the
        currently active Experiment, it will be created and initialized with specified metadata
        parameters. If such a Experiment Run does already exist, it will be retrieved; specifying
        metadata parameters in this case will raise an exception.

        Parameters
        ----------
        expt_run_name : str, optional
            Name of the Experiment Run. If no name is provided, one will be generated.
        desc : str, optional
            Description of the Experiment Run.
        tags : list of str, optional
            Tags of the Experiment Run.
        attrs : dict of str to {None, bool, float, int, str}, optional
            Attributes of the Experiment Run.

        Returns
        -------
        :class:`ExperimentRun`

        Raises
        ------
        ValueError
            If an Experiment Run with `expt_run_name` already exists, but metadata parameters are passed in.
        AttributeError
            If an Experiment is not yet in progress.

        """
        if self.expt is None:
            raise AttributeError("an experiment must first in progress")

        return ExperimentRun(self._auth, self._socket,
                             self.proj._id, self.expt._id, expt_run_name,
                             desc, tags, attrs)


class Project:
    """
    Object representing a machine learning Project.

    This class provides read/write functionality for Project metadata and access to its Experiment
    Runs.

    There should not be a need to instantiate this class directly; please use
    :meth:`ModelDBClient.set_project`.

    Attributes
    ----------
    name : str
        Name of this Project.

    """
    def __init__(self, auth, socket,
                 proj_name=None,
                 desc=None, tags=None, attrs=None,
                 *, _proj_id=None):
        if proj_name is not None and _proj_id is not None:
            raise ValueError("cannot specify both `proj_name` and `_proj_id`")

        if _proj_id is not None:
            proj = Project._get(auth, socket, _proj_id=_proj_id)
            if proj is not None:
                print("set existing Project: {}".format(proj.name))
            else:
                raise ValueError("Project with ID {} not found".format(_proj_id))
        else:
            if proj_name is None:
                proj_name = Project._generate_default_name()
            proj = Project._get(auth, socket, proj_name)
            if proj is not None:
                if any(param is not None for param in (desc, tags, attrs)):
                    raise ValueError("Project with name {} already exists;"
                                     " cannot initialize `desc`, `tags`, or `attrs`".format(proj_name))
                print("set existing Project: {}".format(proj.name))
            else:
                proj = Project._create(auth, socket, proj_name, desc, tags, attrs)
                print("created new Project: {}".format(proj.name))

        self._auth = auth
        self._socket = socket
        self._id = proj.id

    @property
    def name(self):
        Message = _ProjectService.GetProjectById
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/project/getProjectById".format(self._socket),
                                params=data, headers=self._auth)
        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.project.name
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    @staticmethod
    def _generate_default_name():
        return "Project {}".format(str(time.time()).replace('.', ''))

    @staticmethod
    def _get(auth, socket, proj_name=None, *, _proj_id=None):
        if _proj_id is not None:
            Message = _ProjectService.GetProjectById
            msg = Message(id=_proj_id)
            data = _utils.proto_to_json(msg)
            response = requests.get("http://{}/v1/project/getProjectById".format(socket),
                                    params=data, headers=auth)

            if response.ok:
                response_msg = _utils.json_to_proto(response.json(), Message.Response)
                return response_msg.project
            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))
        elif proj_name is not None:
            Message = _ProjectService.GetProjectByName
            msg = Message(name=proj_name)
            data = _utils.proto_to_json(msg)
            response = requests.get("http://{}/v1/project/getProjectByName".format(socket),
                                    params=data, headers=auth)

            if response.ok:
                response_msg = _utils.json_to_proto(response.json(), Message.Response)
                return response_msg.project_by_user[0]
            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))
        else:
            raise ValueError("insufficient arguments")

    @staticmethod
    def _create(auth, socket, proj_name, desc=None, tags=None, attrs=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value))
                     for key, value in attrs.items()]

        Message = _ProjectService.CreateProject
        msg = Message(name=proj_name, description=desc, tags=tags, metadata=attrs)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/project/createProject".format(socket),
                                 json=data, headers=auth)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.project
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def find(self, where, ret_all_info=False):
        """
        Gets the Experiment Runs from this Project that match predicates `where`.

        A predicate in `where` is a string containing a simple boolean expression consisting of:

            - a dot-delimited Experiment Run property such as ``metrics.accuracy``
            - a Python boolean operator such as ``>=``
            - a literal value such as ``.8``

        Parameters
        ----------
        where : str or list of str
            Predicates specifying Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> proj.find(["code_version == '0.2.1'",
        ...            "hyperparameters.hidden size == 256",
        ...            "metrics.accuracy >= .8"])
        <ExperimentRuns containing 3 runs>

        """
        expt_runs = ExperimentRuns(self._auth, self._socket)
        return expt_runs.find(where, ret_all_info, _proj_id=self._id)

    def top_k(self, key, k, ret_all_info=False):
        """
        Gets the Experiment Runs from this Project with the `k` highest `key`\ s.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> proj.top_k("metrics.accuracy", 3)
        <ExperimentRuns containing 3 runs>

        """
        expt_runs = ExperimentRuns(self._auth, self._socket)
        return expt_runs.top_k(key, k, ret_all_info, _proj_id=self._id)

    def bottom_k(self, key, k, ret_all_info=False):
        """
        Gets the Experiment Runs from this Project with the `k` lowest `key`\ s.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.loss``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> proj.bottom_k("metrics.loss", 3)
        <ExperimentRuns containing 3 runs>

        """
        expt_runs = ExperimentRuns(self._auth, self._socket)
        return expt_runs.bottom_k(key, k, ret_all_info, _proj_id=self._id)


class Experiment:
    """
    Object representing a machine learning Experiment.

    This class provides read/write functionality for Experiment metadata and access to its Experiment
    Runs.

    There should not be a need to instantiate this class directly; please use
    :meth:`ModelDBClient.set_experiment`.

    Attributes
    ----------
    name : str
        Name of this Experiment.

    """
    def __init__(self, auth, socket,
                 proj_id=None, expt_name=None,
                 desc=None, tags=None, attrs=None,
                 *, _expt_id=None):
        if expt_name is not None and _expt_id is not None:
            raise ValueError("cannot specify both `expt_name` and `_expt_id`")

        if _expt_id is not None:
            expt = Experiment._get(auth, socket, _expt_id=_expt_id)
            if expt is not None:
                print("set existing Experiment: {}".format(expt.name))
            else:
                raise ValueError("Experiment with ID {} not found".format(_expt_id))
        elif proj_id is not None:
            if expt_name is None:
                expt_name = Experiment._generate_default_name()
            expt = Experiment._get(auth, socket, proj_id, expt_name)
            if expt is not None:
                if any(param is not None for param in (desc, tags, attrs)):
                    raise ValueError("Experiment with name {} already exists;"
                                     " cannot initialize `desc`, `tags`, or `attrs`".format(expt_name))
                print("set existing Experiment: {}".format(expt.name))
            else:
                expt = Experiment._create(auth, socket, proj_id, expt_name, desc, tags, attrs)
                print("created new Experiment: {}".format(expt.name))
        else:
            raise ValueError("insufficient arguments")

        self._auth = auth
        self._socket = socket
        self._id = expt.id

    @property
    def name(self):
        Message = _ExperimentService.GetExperimentById
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment/getExperimentById".format(self._socket),
                                params=data, headers=self._auth)
        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment.name
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    @staticmethod
    def _generate_default_name():
        return "Experiment {}".format(str(time.time()).replace('.', ''))

    @staticmethod
    def _get(auth, socket, proj_id=None, expt_name=None, *, _expt_id=None):
        if _expt_id is not None:
            Message = _ExperimentService.GetExperimentById
            msg = Message(id=_expt_id)
            data = _utils.proto_to_json(msg)
            response = requests.get("http://{}/v1/experiment/getExperimentById".format(socket),
                                    params=data, headers=auth)
        elif None not in (proj_id, expt_name):
            Message = _ExperimentService.GetExperimentByName
            msg = Message(project_id=proj_id, name=expt_name)
            data = _utils.proto_to_json(msg)
            response = requests.get("http://{}/v1/experiment/getExperimentByName".format(socket),
                                    params=data, headers=auth)
        else:
            raise ValueError("insufficient arguments")

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment
        else:
            if response.status_code == 404 and response.json()['code'] == 5:
                return None
            else:
                raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    @staticmethod
    def _create(auth, socket, proj_id, expt_name, desc=None, tags=None, attrs=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value))
                     for key, value in attrs.items()]

        Message = _ExperimentService.CreateExperiment
        msg = Message(project_id=proj_id, name=expt_name,
                      description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment/createExperiment".format(socket),
                                 json=data, headers=auth)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def find(self, where, ret_all_info=False):
        """
        Gets the Experiment Runs from this Experiment that match predicates `where`.

        A predicate in `where` is a string containing a simple boolean expression consisting of:

            - a dot-delimited Experiment Run property such as ``metrics.accuracy``
            - a Python boolean operator such as ``>=``
            - a literal value such as ``.8``

        Parameters
        ----------
        where : str or list of str
            Predicates specifying Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> expt.find(["code_version == '0.2.1'",
        ...            "hyperparameters.hidden size == 256",
        ...            "metrics.accuracy >= .8"])
        <ExperimentRuns containing 3 runs>

        """
        expt_runs = ExperimentRuns(self._auth, self._socket)
        return expt_runs.find(where, ret_all_info, _expt_id=self._id)

    def top_k(self, key, k, ret_all_info=False):
        """
        Gets the Experiment Runs from this Experiment with the `k` highest `key`\ s.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> expt.top_k("metrics.accuracy", 3)
        <ExperimentRuns containing 3 runs>

        """
        expt_runs = ExperimentRuns(self._auth, self._socket)
        return expt_runs.top_k(key, k, ret_all_info, _expt_id=self._id)

    def bottom_k(self, key, k, ret_all_info=False):
        """
        Gets the Experiment Runs from this Experiment with the `k` lowest `key`\ s.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> expt.bottom_k("metrics.loss", 3)
        <ExperimentRuns containing 3 runs>

        """
        expt_runs = ExperimentRuns(self._auth, self._socket)
        return expt_runs.bottom_k(key, k, ret_all_info, _expt_id=self._id)


class ExperimentRuns:
    """
    ``list``-like object representing a collection of machine learning Experiment Runs.

    This class provides functionality for filtering and sorting its contents.

    There should not be a need to instantiate this class directly; please use other classes' methods
    to access Experiment Runs.

    Warnings
    --------
    After an ``ExperimentRuns`` instance is assigned to a variable, it will be detached from the
    method that created it, and *will never automatically update itself*.

    This is to allow filtering and sorting without modifying the Experiment Runs' parent and vice
    versa.

    The individual ``ExperimentRun``\ s themselves, however, are still synchronized with the backend.

    Examples
    --------
    >>> runs = expt.find("hyperparameters.hidden size == 256")
    >>> len(runs)
    12
    >>> runs += expt.find("hyperparameters.hidden size == 512")
    >>> len(runs)
    24
    >>> runs = runs.find("metrics.accuracy >= .8")
    >>> len(runs)
    5
    >>> runs[0].get_metric("accuracy")
    0.8921755939794525

    """
    _OP_MAP = {'==': _ExperimentRunService.OperatorEnum.EQ,
               '!=': _ExperimentRunService.OperatorEnum.NE,
               '>':  _ExperimentRunService.OperatorEnum.GT,
               '>=': _ExperimentRunService.OperatorEnum.GTE,
               '<':  _ExperimentRunService.OperatorEnum.LT,
               '<=': _ExperimentRunService.OperatorEnum.LTE}
    _OP_PATTERN = re.compile(r"({})".format('|'.join(sorted(_OP_MAP.keys(), key=lambda s: len(s), reverse=True))))

    def __init__(self, auth, socket, expt_run_ids=None):
        self._auth = auth
        self._socket = socket
        self._ids = expt_run_ids if expt_run_ids is not None else []

    def __repr__(self):
        return "<ExperimentRuns containing {} runs>".format(self.__len__())

    def __getitem__(self, key):
        if isinstance(key, int):
            expt_run_id = self._ids[key]
            return ExperimentRun(self._auth, self._socket, _expt_run_id=expt_run_id)
        elif isinstance(key, slice):
            expt_run_ids = self._ids[key]
            return self.__class__(self._auth, self._socket, expt_run_ids)
        else:
            raise TypeError("index must be integer or slice, not {}".format(type(key)))

    def __len__(self):
        return len(self._ids)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return self.__class__(self._auth, self._socket, self._ids + other._ids)
        else:
            return NotImplemented

    def find(self, where, ret_all_info=False, *, _proj_id=None, _expt_id=None):
        """
        Gets the Experiment Runs from this collection that match predicates `where`.

        A predicate in `where` is a string containing a simple boolean expression consisting of:

            - a dot-delimited Experiment Run property such as ``metrics.accuracy``
            - a Python boolean operator such as ``>=``
            - a literal value such as ``.8``

        Parameters
        ----------
        where : str or list of str
            Predicates specifying Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> runs.find(["code_version == '0.2.1'",
        ...            "hyperparameters.hidden size == 256",
        ...            "metrics.accuracy >= .8"])
        <ExperimentRuns containing 3 runs>

        """
        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._auth, self._socket)
            else:
                expt_run_ids = self._ids
        else:
            expt_run_ids = None

        predicates = []
        if isinstance(where, str):
            where = [where]
        for predicate in where:
            # split predicate
            try:
                key, operator, value = map(str.strip, self._OP_PATTERN.split(predicate, maxsplit=1))
            except ValueError:
                raise ValueError("predicate `{}` must be a two-operand comparison".format(predicate))

            # cast operator into protobuf enum variant
            operator = self._OP_MAP[operator]

            # parse value
            try:
                expr_node = ast.parse(value, mode='eval')
            except SyntaxError:
                raise ValueError("value `{}` must be a number or string literal".format(value))
            value_node = expr_node.body
            if type(value_node) is ast.Num:
                value = value_node.n
            elif type(value_node) is ast.Str:
                value = value_node.s
            elif type(value_node) is ast.Compare:
                raise ValueError("predicate `{}` must be a two-operand comparison".format(predicate))
            else:
                raise ValueError("value `{}` must be a number or string literal".format(value))

            predicates.append(_ExperimentRunService.KeyValueQuery(key=key, value=_utils.python_to_val_proto(value),
                                                                  operator=operator))
        Message = _ExperimentRunService.FindExperimentRuns
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      predicates=predicates, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/findExperimentRuns".format(self._socket),
                                 json=data, headers=self._auth)
        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            if ret_all_info:
                return response_msg.experiment_runs
            else:
                return self.__class__(self._auth, self._socket,
                                      [expt_run.id for expt_run in response_msg.experiment_runs])
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def sort(self, key, descending=False, ret_all_info=False):
        """
        Sorts the Experiment Runs from this collection by `key`.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        descending : bool, default False
            Order in which to return sorted Experiment Runs.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> runs.sort("metrics.accuracy")
        <ExperimentRuns containing 3 runs>

        """
        if self.__len__() == 0:
            return self.__class__(self._auth, self._socket)

        Message = _ExperimentRunService.SortExperimentRuns
        msg = Message(experiment_run_ids=self._ids,
                      sort_key=key, ascending=not descending, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/sortExperimentRuns".format(self._socket),
                                params=data, headers=self._auth)
        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            if ret_all_info:
                return response_msg.experiment_runs
            else:
                return self.__class__(self._auth, self._socket,
                                      [expt_run.id for expt_run in response_msg.experiment_runs])
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def top_k(self, key, k, ret_all_info=False, *, _proj_id=None, _expt_id=None):
        """
        Gets the Experiment Runs from this collection with the `k` highest `key`\ s.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> runs.top_k("metrics.accuracy", 3)
        <ExperimentRuns containing 3 runs>

        """
        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._auth, self._socket)
            else:
                expt_run_ids = self._ids
        else:
            expt_run_ids = None

        Message = _ExperimentRunService.TopExperimentRunsSelector
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      sort_key=key, ascending=False, top_k=k, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getTopExperimentRuns".format(self._socket),
                                params=data, headers=self._auth)
        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            if ret_all_info:
                return response_msg.experiment_runs
            else:
                return self.__class__(self._auth, self._socket,
                                      [expt_run.id for expt_run in response_msg.experiment_runs])
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def bottom_k(self, key, k, ret_all_info=False, *, _proj_id=None, _expt_id=None):
        """
        Gets the Experiment Runs from this collection with the `k` lowest `key`\ s.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf` `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> runs.bottom_k("metrics.loss", 3)
        <ExperimentRuns containing 3 runs>

        """
        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._auth, self._socket)
            else:
                expt_run_ids = self._ids
        else:
            expt_run_ids = None

        Message = _ExperimentRunService.TopExperimentRunsSelector
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      sort_key=key, ascending=True, top_k=k, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getTopExperimentRuns".format(self._socket),
                                params=data, headers=self._auth)
        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            if ret_all_info:
                return response_msg.experiment_runs
            else:
                return self.__class__(self._auth, self._socket,
                                      [expt_run.id for expt_run in response_msg.experiment_runs])
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))


class ExperimentRun:
    """
    Object representing a machine learning Experiment Run.

    This class provides read/write functionality for Experiment Run metadata.

    There should not be a need to instantiate this class directly; please use
    :meth:`ModelDBClient.set_experiment_run`.

    Attributes
    ----------
    name : str
        Name of this Experiment Run.

    """
    def __init__(self, auth, socket,
                 proj_id=None, expt_id=None, expt_run_name=None,
                 desc=None, tags=None, attrs=None,
                 *, _expt_run_id=None):
        if expt_run_name is not None and _expt_run_id is not None:
            raise ValueError("cannot specify both `expt_run_name` and `_expt_run_id`")

        if _expt_run_id is not None:
            expt_run = ExperimentRun._get(auth, socket, _expt_run_id=_expt_run_id)
            if expt_run is not None:
                pass
            else:
                raise ValueError("ExperimentRun with ID {} not found".format(_expt_run_id))
        elif None not in (proj_id, expt_id):
            if expt_run_name is None:
                expt_run_name = ExperimentRun._generate_default_name()
            expt_run = ExperimentRun._get(auth, socket, proj_id, expt_id, expt_run_name)
            if expt_run is not None:
                if any(param is not None for param in (desc, tags, attrs)):
                    raise ValueError("ExperimentRun with name {} already exists;"
                                     " cannot initialize `desc`, `tags`, or `attrs`".format(expt_run_name))
                pass
            else:
                expt_run = ExperimentRun._create(auth, socket, proj_id, expt_id, expt_run_name, desc, tags, attrs)
        else:
            raise ValueError("insufficient arguments")

        self._auth = auth
        self._socket = socket
        self._id = expt_run.id

    @property
    def name(self):
        Message = _ExperimentRunService.GetExperimentRunById
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getExperimentRunById".format(self._socket),
                                params=data, headers=self._auth)
        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment_run.name
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    @staticmethod
    def _generate_default_name():
        return "ExperimentRun {}".format(str(time.time()).replace('.', ''))

    @staticmethod
    def _get(auth, socket, proj_id=None, expt_id=None, expt_run_name=None, *, _expt_run_id=None):
        if _expt_run_id is not None:
            Message = _ExperimentRunService.GetExperimentRunById
            msg = Message(id=_expt_run_id)
            data = _utils.proto_to_json(msg)
            response = requests.get("http://{}/v1/experiment-run/getExperimentRunById".format(socket),
                                    params=data, headers=auth)
        elif None not in (proj_id, expt_id, expt_run_name):
            Message = _ExperimentRunService.GetExperimentRunsInProject
            msg = Message(project_id=proj_id)
            data = _utils.proto_to_json(msg)
            response = requests.get("http://{}/v1/experiment-run/getExperimentRunsInProject".format(socket),
                                    params=data, headers=auth)
            if not response.ok:
                raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))
            else:
                if 'experiment_runs' in response.json():
                    response_msg = _utils.json_to_proto(response.json(), Message.Response)
                    result = [expt_run
                              for expt_run in response_msg.experiment_runs
                              if expt_run.name == expt_run_name]
                    return result[-1] if len(result) else None
                else:  # no expt_runs in proj
                    return None
        else:
            raise ValueError("insufficient arguments")

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment_run
        else:
            if response.status_code == 404 and response.json()['code'] == 5:
                return None
            else:
                raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    @staticmethod
    def _create(auth, socket, proj_id, expt_id, expt_run_name, desc=None, tags=None, attrs=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value))
                     for key, value in attrs.items()]

        Message = _ExperimentRunService.CreateExperimentRun
        msg = Message(project_id=proj_id, experiment_id=expt_id, name=expt_run_name,
                      description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/createExperimentRun".format(socket),
                                 json=data, headers=auth)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment_run
        else:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def log_attribute(self, name, value):
        """
        Logs an attribute to this Experiment Run.

        Attributes are descriptive metadata, such as the team responsible for this model or the
        expected training time.

        Parameters
        ----------
        name : str
            Name of the attribute.
        value : one of {None, bool, float, int, str}
            Value of the attribute.

        """
        attribute = _CommonService.KeyValue(key=name, value=_utils.python_to_val_proto(value))
        msg = _ExperimentRunService.LogAttribute(id=self._id, attribute=attribute)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/logAttribute".format(self._socket),
                                 json=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def get_attribute(self, name):
        """
        Gets the attribute with name `name` from this Experiment Run.

        Parameters
        ----------
        name : str
            Name of the attribute.

        Returns
        -------
        one of {None, bool, float, int, str}
            Value of the attribute.

        """
        Message = _CommonService.GetAttributes
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getAttributes".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {attribute.key: _utils.val_proto_to_python(attribute.value)
                for attribute in response_msg.attributes}[name]

    def get_attributes(self):
        """
        Gets all attributes from this Experiment Run.

        Returns
        -------
        dict of str to {None, bool, float, int, str}
            Names and values of all attributes.

        """
        Message = _CommonService.GetAttributes
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getAttributes".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {attribute.key: _utils.val_proto_to_python(attribute.value)
                for attribute in response_msg.attributes}

    def log_metric(self, name, value):
        """
        Logs a metric to this Experiment Run.

        Metrics are unique performance metadata, such as accuracy or loss on the full training set.

        If the metadatum of interest might recur, :meth:`.log_observation` should be used instead.

        Parameters
        ----------
        name : str
            Name of the metric.
        value : one of {None, bool, float, int, str}
            Value of the metric.

        """
        metric = _CommonService.KeyValue(key=name, value=_utils.python_to_val_proto(value))
        msg = _ExperimentRunService.LogMetric(id=self._id, metric=metric)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/logMetric".format(self._socket),
                                 json=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def get_metric(self, name):
        """
        Gets the metric with name `name` from this Experiment Run.

        Parameters
        ----------
        name : str
            Name of the metric.

        Returns
        -------
        one of {None, bool, float, int, str}
            Value of the metric.

        """
        Message = _ExperimentRunService.GetMetrics
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getMetrics".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {metric.key: _utils.val_proto_to_python(metric.value)
                for metric in response_msg.metrics}[name]

    def get_metrics(self):
        """
        Gets all metrics from this Experiment Run.

        Returns
        -------
        dict of str to {None, bool, float, int, str}
            Names and values of all Metrics.

        """
        Message = _ExperimentRunService.GetMetrics
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getMetrics".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {metric.key: _utils.val_proto_to_python(metric.value)
                for metric in response_msg.metrics}

    def log_hyperparameter(self, name, value):
        """
        Logs a hyperparameter to this Experiment Run.

        Hyperparameters are model configuration metadata, such as the loss function or the
        regularization penalty.

        Parameters
        ----------
        name : str
            Name of the hyperparameter.
        value : one of {None, bool, float, int, str}
            Value of the hyperparameter.

        """
        hyperparameter = _CommonService.KeyValue(key=name, value=_utils.python_to_val_proto(value))
        msg = _ExperimentRunService.LogHyperparameter(id=self._id, hyperparameter=hyperparameter)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/logHyperparameter".format(self._socket),
                                 json=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def get_hyperparameter(self, name):
        """
        Gets the hyperparameter with name `name` from this Experiment Run.

        Parameters
        ----------
        name : str
            Name of the hyperparameter.

        Returns
        -------
        one of {None, bool, float, int, str}
            Value of the hyperparameter.

        """
        Message = _ExperimentRunService.GetHyperparameters
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getHyperparameters".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {hyperparameter.key: _utils.val_proto_to_python(hyperparameter.value)
                for hyperparameter in response_msg.hyperparameters}[name]

    def get_hyperparameters(self):
        """
        Gets all hyperparameters from this Experiment Run.

        Returns
        -------
        dict of str to {None, bool, float, int, str}
            Names and values of all Hyperparameters.

        """
        Message = _ExperimentRunService.GetHyperparameters
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getHyperparameters".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {hyperparameter.key: _utils.val_proto_to_python(hyperparameter.value)
                for hyperparameter in response_msg.hyperparameters}

    def log_dataset(self, name, path):
        """
        Logs the file system path of a dataset to this Experiment Run.

        Datasets are model inputs, such as a test or validation set of grayscale images.

        Parameters
        ----------
        name : str
            Name of the dataset.
        path : str
            File system path of the dataset.

        """
        dataset = _CommonService.Artifact(key=name, path=path,
                                          artifact_type=_CommonService.ArtifactTypeEnum.DATA)
        msg = _ExperimentRunService.LogDataset(id=self._id, dataset=dataset)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/logDataset".format(self._socket),
                                 json=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def get_dataset(self, name):
        """
        Gets the file system path of the dataset with name `name` from this Experiment Run.

        Parameters
        ----------
        name : str
            Name of the dataset.

        Returns
        -------
        str
            File system path of the dataset.

        """
        Message = _ExperimentRunService.GetDatasets
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getDatasets".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {dataset.key: dataset.path for dataset in response_msg.datasets}[name]

    def get_datasets(self):
        """
        Gets file system paths of all datasets from this Experiment Run.

        Returns
        -------
        dict of str to str
            File system paths of all datasets.

        """
        Message = _ExperimentRunService.GetDatasets
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getDatasets".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {dataset.key: dataset.path for dataset in response_msg.datasets}

    def log_model(self, name, path, model=None):
        """
        Logs the file system path of a model to this Experiment Run.

        Models are the result of the training procedure, such as a pickled support vector machine
        or a neural network's weight tensors.

        Parameters
        ----------
        name : str
            Name of the model.
        path : str
            File system path of the model.
        model : object (optional)
            Model object to be logged.

        """
        if model is not None:
            joblib.dump(model, path)
        model_artifact = _CommonService.Artifact(key=name, path=path,
                                        artifact_type=_CommonService.ArtifactTypeEnum.MODEL)
        msg = _ExperimentRunService.LogArtifact(id=self._id, artifact=model_artifact)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/logArtifact".format(self._socket),
                                 json=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def get_model(self, name):
        """
        Gets the file system path of the model with name `name` from this Experiment Run.

        Parameters
        ----------
        name : str
            Name of the model.

        Returns
        -------
        str
            File system path of the model.

        """
        Message = _ExperimentRunService.GetArtifacts
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getArtifacts".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {artifact.key: artifact.path
                for artifact in response_msg.artifacts
                if artifact.artifact_type == _CommonService.ArtifactTypeEnum.MODEL}[name]

    def get_models(self):
        """
        Gets file system paths of all models from this Experiment Run.

        Returns
        -------
        dict of str to str
            File system paths of all models.

        """
        Message = _ExperimentRunService.GetArtifacts
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getArtifacts".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {artifact.key: artifact.path
                for artifact in response_msg.artifacts
                if artifact.artifact_type == _CommonService.ArtifactTypeEnum.MODEL}

    def log_image(self, name, path):
        """
        Logs the file system path of an image to this Experiment Run.

        Images are graphics, such as a graph of training loss across epochs or images generated by
        the model.

        Parameters
        ----------
        name : str
            Name of the image.
        path : str
            File system path of the image.

        """
        image = _CommonService.Artifact(key=name, path=path,
                                        artifact_type=_CommonService.ArtifactTypeEnum.IMAGE)
        msg = _ExperimentRunService.LogArtifact(id=self._id, artifact=image)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/logArtifact".format(self._socket),
                                 json=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def get_image(self, name):
        """
        Gets the file system path of the image with name `name` from this Experiment Run.

        Parameters
        ----------
        name : str
            Name of the image.

        Returns
        -------
        str
            File system path of the image.

        """
        Message = _ExperimentRunService.GetArtifacts
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getArtifacts".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {artifact.key: artifact.path
                for artifact in response_msg.artifacts
                if artifact.artifact_type == _CommonService.ArtifactTypeEnum.IMAGE}[name]

    def get_images(self):
        """
        Gets file system paths of all images from this Experiment Run.

        Returns
        -------
        dict of str to str
            File system paths of all images.

        """
        Message = _ExperimentRunService.GetArtifacts
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getArtifacts".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return {artifact.key: artifact.path
                for artifact in response_msg.artifacts
                if artifact.artifact_type == _CommonService.ArtifactTypeEnum.IMAGE}

    def log_observation(self, name, value):
        """
        Logs an observation to this Experiment Run.

        Observations are recurring metadata that are repeatedly measured over time, such as batch
        losses over an epoch or memory usage.

        Parameters
        ----------
        name : str
            Name of the observation.
        value : one of {None, bool, float, int, str}
            Value of the observation.

        """
        attribute = _CommonService.KeyValue(key=name, value=_utils.python_to_val_proto(value))
        observation = _ExperimentRunService.Observation(attribute=attribute)  # TODO: support Artifacts
        msg = _ExperimentRunService.LogObservation(id=self._id, observation=observation)
        data = _utils.proto_to_json(msg)
        response = requests.post("http://{}/v1/experiment-run/logObservation".format(self._socket),
                                 json=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

    def get_observation(self, name):
        """
        Gets the observation series with name `name` from this Experiment Run.

        Parameters
        ----------
        name : str
            Name of observation series.

        Returns
        -------
        list of {None, bool, float, int, str}
            Values of observation series.

        """
        Message = _ExperimentRunService.GetObservations
        msg = Message(id=self._id, observation_key=name)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getObservations".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if len(response_msg.observations) == 0:
            raise KeyError(name)
        else:
            return [_utils.val_proto_to_python(observation.attribute.value)
                    for observation in response_msg.observations]  # TODO: support Artifacts

    def get_observations(self):
        """
        Gets all observations from this Experiment Run.

        Returns
        -------
        dict of str to list of {None, bool, float, int, str}
            Names and values of all observation series.

        """
        Message = _ExperimentRunService.GetExperimentRunById
        msg = Message(id=self._id)
        data = _utils.proto_to_json(msg)
        response = requests.get("http://{}/v1/experiment-run/getExperimentRunById".format(self._socket),
                                params=data, headers=self._auth)
        if not response.ok:
            raise requests.HTTPError("{}: {}".format(response.status_code, response.reason))

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        observations = {}
        for observation in response_msg.experiment_run.observations:  # TODO: support Artifacts
            key = observation.attribute.key
            value = observation.attribute.value
            observations.setdefault(key, []).append(_utils.val_proto_to_python(value))
        return observations
