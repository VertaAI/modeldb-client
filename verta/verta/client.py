import six
import six.moves.cPickle as pickle
from six.moves.urllib.parse import urlparse

import ast
import os
import re
import warnings

import PIL
import requests
from urllib3.util.retry import Retry

from ._protos.public.modeldb import CommonService_pb2 as _CommonService
from ._protos.public.modeldb import ProjectService_pb2 as _ProjectService
from ._protos.public.modeldb import ExperimentService_pb2 as _ExperimentService
from ._protos.public.modeldb import ExperimentRunService_pb2 as _ExperimentRunService
from . import _utils
from . import _artifact_utils
from . import utils


class Client:
    """
    Object for interfacing with the ModelDB backend.

    This class provides functionality for starting/resuming Projects, Experiments, and Experiment
    Runs.

    Parameters
    ----------
    host : str
        Hostname of the node running the ModelDB backend.
    port : str or int, optional
        Port number to which the ModelDB backend is listening.
    email : str, optional
        Authentication credentials for managed service. If this does not sound familiar, then there
        is no need to set it.
    dev_key : str, optional
        Authentication credentials for managed service. If this does not sound familiar, then there
        is no need to set it.
    max_retries : int, default 5
        Maximum number of times to retry a request on a connection failure. This only attempts retries
        on HTTP codes {403, 503, 504} which commonly occur during back end connection lapses.

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

    def __init__(self, host, port=None, email=None, dev_key=None, max_retries=5):
        if email is None and 'VERTA_EMAIL' in os.environ:
            email = os.environ['VERTA_EMAIL']
            print("set email from environment")
        if dev_key is None and 'VERTA_DEV_KEY' in os.environ:
            dev_key = os.environ.get('VERTA_DEV_KEY')
            print("set developer key from environment")

        if email is None and dev_key is None:
            auth = None
            scheme = "http"
        elif email is not None and dev_key is not None:
            auth = {self._GRPC_PREFIX+'email': email,
                    self._GRPC_PREFIX+'developer_key': dev_key,
                    self._GRPC_PREFIX+'source': "PythonClient"}
            scheme = "https"
        else:
            raise ValueError("`email` and `dev_key` must be provided together")

        host = urlparse(host)
        if host.netloc == '':
            # We passed a host that cannot be resolved into a basic URL. Assume it's the right path
            host = host.path
        else:
            # Otherwise, just get the netlocation, which contains the hostname and port
            # TODO(conrado): support subpaths? (e.g. example.com/backend)
            host = host.netloc

        # define connection retry configuration
        retry = Retry(total=max_retries,
                      backoff_factor=1,  # each retry waits (2**retry_num) seconds
                      method_whitelist=False,  # retry on all HTTP methods
                      status_forcelist=(403, 503, 504),  # only retry on these status codes
                      raise_on_redirect=False,  # return Response instead of raising after max retries
                      raise_on_status=False)  # return Response instead of raising after max retries
        # TODO: retry on 404s, but only if we're sure it's not legitimate e.g. from a GET

        # verify connection
        socket = host if port is None else "{}:{}".format(host, port)
        try:
            response = requests.get("{}://{}/v1/project/verifyConnection".format(scheme, socket), headers=auth)
        except requests.ConnectionError:
            raise requests.ConnectionError("connection failed; please check `host` and `port`")
        response.raise_for_status()
        print("connection successfully established")

        self._auth = auth
        self._scheme = scheme
        self._socket = socket
        self._retry = retry

        self.proj = None
        self.expt = None

    @property
    def max_retries(self):
        return self._retry.total

    @max_retries.setter
    def max_retries(self, value):
        self._retry.total = value

    @property
    def expt_runs(self):
        if self.expt is None:
            return None
        else:
            Message = _ExperimentRunService.GetExperimentRunsInProject
            msg = Message(project_id=self.proj.id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment-run/getExperimentRunsInProject".format(self._scheme, self._socket),
                                           self._auth, self._retry,
                                           params=data)
            response.raise_for_status()

            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            expt_run_ids = [expt_run.id
                            for expt_run in response_msg.experiment_runs
                            if expt_run.experiment_id == self.expt.id]
            return ExperimentRuns(self._auth, self._socket, self._retry, expt_run_ids)

    def set_project(self, name=None, desc=None, tags=None, attrs=None, id=None):
        """
        Attaches a Project to this Client.

        If an accessible Project with name `name` does not already exist, it will be created
        and initialized with specified metadata parameters. If such a Project does already exist,
        it will be retrieved; specifying metadata parameters in this case will raise an exception.

        If an Experiment is already attached to this Client, it will be detached.

        Parameters
        ----------
        name : str, optional
            Name of the Project. If no name is provided, one will be generated.
        desc : str, optional
            Description of the Project.
        tags : list of str, optional
            Tags of the Project.
        attrs : dict of str to {None, bool, float, int, str}, optional
            Attributes of the Project.
        id : str
            ID of the project. This parameter cannot be provided alongside `name`, and other
            parameters will be ignored.

        Returns
        -------
        :class:`Project`

        Raises
        ------
        ValueError
            If a Project with `name` already exists, but metadata parameters are passed in.

        """
        # if proj already in progress, reset expt
        if self.proj is not None:
            self.expt = None

        proj = Project(self._auth, self._socket, self._retry,
                       name,
                       desc, tags, attrs,
                       id)

        self.proj = proj
        return proj

    def set_experiment(self, name=None, desc=None, tags=None, attrs=None):
        """
        Attaches an Experiment under the currently active Project to this Client.

        If an accessible Experiment with name `name` does not already exist under the currently
        active Project, it will be created and initialized with specified metadata parameters. If
        such an Experiment does already exist, it will be retrieved; specifying metadata parameters
        in this case will raise an exception.

        Parameters
        ----------
        name : str, optional
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
            If an Experiment with `name` already exists, but metadata parameters are passed in.
        AttributeError
            If a Project is not yet in progress.

        """
        if self.proj is None:
            raise AttributeError("a project must first be in progress")

        expt = Experiment(self._auth, self._socket, self._retry,
                          self.proj.id, name,
                          desc, tags, attrs)

        self.expt = expt
        return expt

    def set_experiment_run(self, name=None, desc=None, tags=None, attrs=None):
        """
        Attaches an Experiment Run under the currently active Experiment to this Client.

        If an accessible Experiment Run with name `name` does not already exist under the
        currently active Experiment, it will be created and initialized with specified metadata
        parameters. If such a Experiment Run does already exist, it will be retrieved; specifying
        metadata parameters in this case will raise an exception.

        Parameters
        ----------
        name : str, optional
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
            If an Experiment Run with `name` already exists, but metadata parameters are passed in.
        AttributeError
            If an Experiment is not yet in progress.

        """
        if self.expt is None:
            raise AttributeError("an experiment must first be in progress")

        return ExperimentRun(self._auth, self._socket, self._retry,
                             self.proj.id, self.expt.id, name,
                             desc, tags, attrs)


class Project:
    """
    Object representing a machine learning Project.

    This class provides read/write functionality for Project metadata and access to its Experiment
    Runs.

    There should not be a need to instantiate this class directly; please use
    :meth:`Client.set_project`.

    Attributes
    ----------
    id : str
        ID of this Project.
    name : str
        Name of this Project.
    expt_runs : :class:`ExperimentRuns`
        Experiment Runs under this Project.

    """
    def __init__(self, auth, socket, retry,
                 proj_name=None,
                 desc=None, tags=None, attrs=None,
                 _proj_id=None):
        if proj_name is not None and _proj_id is not None:
            raise ValueError("cannot specify both `proj_name` and `_proj_id`")

        if _proj_id is not None:
            proj = Project._get(auth, socket, retry, _proj_id=_proj_id)
            if proj is not None:
                print("set existing Project: {}".format(proj.name))
            else:
                raise ValueError("Project with ID {} not found".format(_proj_id))
        else:
            if proj_name is None:
                proj_name = Project._generate_default_name()
            try:
                proj = Project._create(auth, socket, retry, proj_name, desc, tags, attrs)
            except requests.HTTPError as e:
                if e.response.status_code == 409:  # already exists
                    if any(param is not None for param in (desc, tags, attrs)):
                        warnings.warn("Project with name {} already exists;"
                                      " cannot initialize `desc`, `tags`, or `attrs`".format(proj_name))
                    proj = Project._get(auth, socket, retry, proj_name)
                    print("set existing Project: {}".format(proj.name))
                else:
                    raise e
            else:
                print("created new Project: {}".format(proj.name))

        self._auth = auth
        self._scheme = "http" if auth is None else "https"
        self._socket = socket
        self._retry = retry
        self.id = proj.id

    def __repr__(self):
        return "<Project \"{}\">".format(self.name)

    @property
    def name(self):
        Message = _ProjectService.GetProjectById
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/project/getProjectById".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.project.name

    @property
    def expt_runs(self):
        # get runs in this Project
        Message = _ExperimentRunService.GetExperimentRunsInProject
        msg = Message(project_id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunsInProject".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        expt_run_ids = [expt_run.id
                        for expt_run
                        in _utils.json_to_proto(response.json(), Message.Response).experiment_runs]
        return ExperimentRuns(self._auth, self._socket, self._retry, expt_run_ids)

    @staticmethod
    def _generate_default_name():
        return "Proj {}".format(_utils.generate_default_name())

    @staticmethod
    def _get(auth, socket, retry, proj_name=None, _proj_id=None):
        scheme = "http" if auth is None else "https"

        if _proj_id is not None:
            Message = _ProjectService.GetProjectById
            msg = Message(id=_proj_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/project/getProjectById".format(scheme, socket),
                                           auth, retry,
                                           params=data)

            if response.ok:
                response_msg = _utils.json_to_proto(response.json(), Message.Response)
                return response_msg.project
            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    response.raise_for_status()
        elif proj_name is not None:
            Message = _ProjectService.GetProjectByName
            msg = Message(name=proj_name)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/project/getProjectByName".format(scheme, socket),
                                           auth, retry,
                                           params=data)

            if response.ok:
                response_msg = _utils.json_to_proto(response.json(), Message.Response)
                return response_msg.project_by_user
            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    response.raise_for_status()
        else:
            raise ValueError("insufficient arguments")

    @staticmethod
    def _create(auth, socket, retry, proj_name, desc=None, tags=None, attrs=None):
        scheme = "http" if auth is None else "https"

        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        Message = _ProjectService.CreateProject
        msg = Message(name=proj_name, description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/project/createProject".format(scheme, socket),
                                       auth, retry,
                                       json=data)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.project
        else:
            response.raise_for_status()


class Experiment:
    """
    Object representing a machine learning Experiment.

    This class provides read/write functionality for Experiment metadata and access to its Experiment
    Runs.

    There should not be a need to instantiate this class directly; please use
    :meth:`Client.set_experiment`.

    Attributes
    ----------
    id : str
        ID of this Experiment.
    name : str
        Name of this Experiment.
    expt_runs : :class:`ExperimentRuns`
        Experiment Runs under this Experiment.

    """
    def __init__(self, auth, socket, retry,
                 proj_id=None, expt_name=None,
                 desc=None, tags=None, attrs=None,
                 _expt_id=None):
        if expt_name is not None and _expt_id is not None:
            raise ValueError("cannot specify both `expt_name` and `_expt_id`")

        if _expt_id is not None:
            expt = Experiment._get(auth, socket, retry, _expt_id=_expt_id)
            if expt is not None:
                print("set existing Experiment: {}".format(expt.name))
            else:
                raise ValueError("Experiment with ID {} not found".format(_expt_id))
        elif proj_id is not None:
            if expt_name is None:
                expt_name = Experiment._generate_default_name()
            try:
                expt = Experiment._create(auth, socket, retry, proj_id, expt_name, desc, tags, attrs)
            except requests.HTTPError as e:
                if e.response.status_code == 409:  # already exists
                    if any(param is not None for param in (desc, tags, attrs)):
                        warnings.warn("Experiment with name {} already exists;"
                                      " cannot initialize `desc`, `tags`, or `attrs`".format(expt_name))
                    expt = Experiment._get(auth, socket, retry, proj_id, expt_name)
                    print("set existing Experiment: {}".format(expt.name))
                else:
                    raise e
            else:
                print("created new Experiment: {}".format(expt.name))
        else:
            raise ValueError("insufficient arguments")

        self._auth = auth
        self._scheme = "http" if auth is None else "https"
        self._socket = socket
        self._retry = retry
        self.id = expt.id

    def __repr__(self):
        return "<Experiment \"{}\">".format(self.name)

    @property
    def name(self):
        Message = _ExperimentService.GetExperimentById
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment/getExperimentById".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.experiment.name

    @property
    def expt_runs(self):
        # get runs in this Experiment
        Message = _ExperimentRunService.GetExperimentRunsInExperiment
        msg = Message(experiment_id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunsInExperiment".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        expt_run_ids = [expt_run.id
                        for expt_run
                        in _utils.json_to_proto(response.json(), Message.Response).experiment_runs]
        return ExperimentRuns(self._auth, self._socket, self._retry, expt_run_ids)

    @staticmethod
    def _generate_default_name():
        return "Expt {}".format(_utils.generate_default_name())

    @staticmethod
    def _get(auth, socket, retry, proj_id=None, expt_name=None, _expt_id=None):
        scheme = "http" if auth is None else "https"

        if _expt_id is not None:
            Message = _ExperimentService.GetExperimentById
            msg = Message(id=_expt_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment/getExperimentById".format(scheme, socket),
                                           auth, retry,
                                           params=data)
        elif None not in (proj_id, expt_name):
            Message = _ExperimentService.GetExperimentByName
            msg = Message(project_id=proj_id, name=expt_name)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment/getExperimentByName".format(scheme, socket),
                                           auth, retry,
                                           params=data)
        else:
            raise ValueError("insufficient arguments")

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment
        else:
            if response.status_code == 404 and response.json()['code'] == 5:
                return None
            else:
                response.raise_for_status()

    @staticmethod
    def _create(auth, socket, retry, proj_id, expt_name, desc=None, tags=None, attrs=None):
        scheme = "http" if auth is None else "https"

        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        Message = _ExperimentService.CreateExperiment
        msg = Message(project_id=proj_id, name=expt_name,
                      description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment/createExperiment".format(scheme, socket),
                                       auth, retry,
                                       json=data)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment
        else:
            response.raise_for_status()


class ExperimentRuns:
    """
    ``list``-like object representing a collection of machine learning Experiment Runs.

    This class provides functionality for filtering and sorting its contents.

    There should not be a need to instantiate this class directly; please use other classes'
    attributes to access Experiment Runs.

    Warnings
    --------
    After an ``ExperimentRuns`` instance is assigned to a variable, it will be detached from the
    method that created it, and *will never automatically update itself*.

    This is to allow filtering and sorting without modifying the Experiment Runs' parent and vice
    versa.

    For example, this behavior may be surprising:

    >>> runs = expt.expt_runs
    >>> runs
    <ExperimentRuns containing 10 runs>
    >>> new_run = client.set_experiment_run()
    >>> expt.expt_runs  # updated
    <ExperimentRuns containing 11 runs>
    >>> runs  # still 10
    <ExperimentRuns containing 10 runs>

    The individual ``ExperimentRun``\ s themselves, however, are still synchronized with the backend.

    Examples
    --------
    >>> runs = expt.find("hyperparameters.hidden_size == 256")
    >>> len(runs)
    12
    >>> runs += expt.find("hyperparameters.hidden_size == 512")
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
    _OP_PATTERN = re.compile(r"({})".format('|'.join(sorted(six.viewkeys(_OP_MAP), key=lambda s: len(s), reverse=True))))

    def __init__(self, auth, socket, retry, expt_run_ids=None):
        self._auth = auth
        self._scheme = "http" if auth is None else "https"
        self._socket = socket
        self._retry = retry
        self._ids = expt_run_ids if expt_run_ids is not None else []

    def __repr__(self):
        return "<ExperimentRuns containing {} runs>".format(self.__len__())

    def __getitem__(self, key):
        if isinstance(key, int):
            expt_run_id = self._ids[key]
            return ExperimentRun(self._auth, self._socket, self._retry, _expt_run_id=expt_run_id)
        elif isinstance(key, slice):
            expt_run_ids = self._ids[key]
            return self.__class__(self._auth, self._socket, self._retry, expt_run_ids)
        else:
            raise TypeError("index must be integer or slice, not {}".format(type(key)))

    def __len__(self):
        return len(self._ids)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            self_ids_set = set(self._ids)
            other_ids = [expt_run_id for expt_run_id in other._ids if expt_run_id not in self_ids_set]
            return self.__class__(self._auth, self._socket, self._retry, self._ids + other_ids)
        else:
            return NotImplemented

    def find(self, where, ret_all_info=False, _proj_id=None, _expt_id=None):
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
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf`
            `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> runs.find(["code_version == '0.2.1'",
        ...            "hyperparameters.hidden_size == 256",
        ...            "metrics.accuracy >= .8"])
        <ExperimentRuns containing 3 runs>

        """
        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._auth, self._socket, self._retry)
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
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/findExperimentRuns".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._auth, self._socket, self._retry,
                                  [expt_run.id for expt_run in response_msg.experiment_runs])

    def sort(self, key, descending=False, ret_all_info=False):
        """
        Sorts the Experiment Runs from this collection by `key`.

        A `key` is a string containing a dot-delimited Experiment Run property such as
        ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        descending : bool, default False
            Order in which to return sorted Experiment Runs.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf`
            `Message`\ s.

        Returns
        -------
        :class:`ExperimentRuns` or iterable of google.protobuf.message.Message

        Examples
        --------
        >>> runs.sort("metrics.accuracy")
        <ExperimentRuns containing 3 runs>

        """
        if self.__len__() == 0:
            return self.__class__(self._auth, self._socket, self._retry)

        Message = _ExperimentRunService.SortExperimentRuns
        msg = Message(experiment_run_ids=self._ids,
                      sort_key=key, ascending=not descending, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/sortExperimentRuns".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._auth, self._socket, self._retry,
                                  [expt_run.id for expt_run in response_msg.experiment_runs])

    def top_k(self, key, k, ret_all_info=False, _proj_id=None, _expt_id=None):
        """
        Gets the Experiment Runs from this collection with the `k` highest `key`\ s.

        A `key` is a string containing a dot-delimited Experiment Run property such as
        ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.
        ret_all_info : bool, default False
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf`
            `Message`\ s.

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
                return self.__class__(self._auth, self._socket, self._retry)
            else:
                expt_run_ids = self._ids
        else:
            expt_run_ids = None

        Message = _ExperimentRunService.TopExperimentRunsSelector
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      sort_key=key, ascending=False, top_k=k, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getTopExperimentRuns".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._auth, self._socket, self._retry,
                                  [expt_run.id for expt_run in response_msg.experiment_runs])

    def bottom_k(self, key, k, ret_all_info=False, _proj_id=None, _expt_id=None):
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
            If False, return an :class:`ExperimentRuns`. Otherwise, return an iterable of `protobuf`
            `Message`\ s.

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
                return self.__class__(self._auth, self._socket, self._retry)
            else:
                expt_run_ids = self._ids
        else:
            expt_run_ids = None

        Message = _ExperimentRunService.TopExperimentRunsSelector
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      sort_key=key, ascending=True, top_k=k, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getTopExperimentRuns".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._auth, self._socket, self._retry,
                                  [expt_run.id for expt_run in response_msg.experiment_runs])


class ExperimentRun:
    """
    Object representing a machine learning Experiment Run.

    This class provides read/write functionality for Experiment Run metadata.

    There should not be a need to instantiate this class directly; please use
    :meth:`Client.set_experiment_run`.

    Attributes
    ----------
    id : str
        ID of this Experiment Run.
    name : str
        Name of this Experiment Run.

    """
    def __init__(self, auth, socket, retry,
                 proj_id=None, expt_id=None, expt_run_name=None,
                 desc=None, tags=None, attrs=None,
                 _expt_run_id=None):
        if expt_run_name is not None and _expt_run_id is not None:
            raise ValueError("cannot specify both `expt_run_name` and `_expt_run_id`")

        if _expt_run_id is not None:
            expt_run = ExperimentRun._get(auth, socket, retry, _expt_run_id=_expt_run_id)
            if expt_run is not None:
                pass
            else:
                raise ValueError("ExperimentRun with ID {} not found".format(_expt_run_id))
        elif None not in (proj_id, expt_id):
            if expt_run_name is None:
                expt_run_name = ExperimentRun._generate_default_name()
            try:
                expt_run = ExperimentRun._create(auth, socket, retry, proj_id, expt_id, expt_run_name, desc, tags, attrs)
            except requests.HTTPError as e:
                if e.response.status_code == 409:  # already exists
                    if any(param is not None for param in (desc, tags, attrs)):
                        warnings.warn("ExperimentRun with name {} already exists;"
                                      " cannot initialize `desc`, `tags`, or `attrs`".format(expt_run_name))
                    expt_run = ExperimentRun._get(auth, socket, retry, expt_id, expt_run_name)
                    print("set existing ExperimentRun: {}".format(expt_run.name))
                else:
                    raise e
            else:
                print("created new ExperimentRun: {}".format(expt_run.name))
        else:
            raise ValueError("insufficient arguments")

        self._auth = auth
        self._scheme = "http" if auth is None else "https"
        self._socket = socket
        self._retry = retry
        self.id = expt_run.id

    def __repr__(self):
        Message = _ExperimentRunService.GetExperimentRunById
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunById".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        run_msg = response_msg.experiment_run
        return '\n'.join((
            "name: {}".format(run_msg.name),
            "url: {}://{}/project/{}/exp-runs/{}".format(self._scheme, self._socket, run_msg.project_id, self.id),
            "description: {}".format(run_msg.description),
            "tags: {}".format(run_msg.tags),
            "attributes: {}".format(_utils.unravel_key_values(run_msg.attributes)),
            "id: {}".format(run_msg.id),
            "experiment id: {}".format(run_msg.experiment_id),
            "project id: {}".format(run_msg.project_id),
            "hyperparameters: {}".format(_utils.unravel_key_values(run_msg.hyperparameters)),
            "observations: {}".format(_utils.unravel_observations(run_msg.observations)),
            "metrics: {}".format(_utils.unravel_key_values(run_msg.metrics)),
            "artifact keys: {}".format(_utils.unravel_artifacts(run_msg.artifacts)),
        ))


    @property
    def name(self):
        Message = _ExperimentRunService.GetExperimentRunById
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunById".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.experiment_run.name

    @staticmethod
    def _generate_default_name():
        return "Run {}".format(_utils.generate_default_name())

    @staticmethod
    def _get(auth, socket, retry, expt_id=None, expt_run_name=None, _expt_run_id=None):
        scheme = "http" if auth is None else "https"

        if _expt_run_id is not None:
            Message = _ExperimentRunService.GetExperimentRunById
            msg = Message(id=_expt_run_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment-run/getExperimentRunById".format(scheme, socket),
                                           auth, retry,
                                           params=data)
        elif None not in (expt_id, expt_run_name):
            Message = _ExperimentRunService.GetExperimentRunByName
            msg = Message(experiment_id=expt_id, name=expt_run_name)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment-run/getExperimentRunByName".format(scheme, socket),
                                           auth, retry,
                                           params=data)
        else:
            raise ValueError("insufficient arguments")

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment_run
        else:
            if response.status_code == 404 and response.json()['code'] == 5:
                return None
            else:
                response.raise_for_status()

    @staticmethod
    def _create(auth, socket, retry, proj_id, expt_id, expt_run_name, desc=None, tags=None, attrs=None):
        scheme = "http" if auth is None else "https"

        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        Message = _ExperimentRunService.CreateExperimentRun
        msg = Message(project_id=proj_id, experiment_id=expt_id, name=expt_run_name,
                      description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/createExperimentRun".format(scheme, socket),
                                       auth, retry,
                                       json=data)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment_run
        else:
            response.raise_for_status()

    def _get_url_for_artifact(self, key, method):
        """
        Obtains a URL to use for accessing stored artifacts.

        Parameters
        ----------
        key : str
            Name of the artifact.
        method : {'GET', 'PUT'}
            HTTP method to request for the generated URL.

        Returns
        -------
        str
            Generated URL.

        """
        if method.upper() not in ("GET", "PUT"):
            raise ValueError("`method` must be one of {'GET', 'PUT'}")

        Message = _ExperimentRunService.GetUrlForArtifact
        msg = Message(id=self.id, key=key, method=method.upper())
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/getUrlForArtifact".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.url

    def _log_artifact(self, key, artifact, artifact_type):
        """
        Logs an artifact to this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the artifact.
        artifact : str or file-like or object
            Artifact or some representation thereof.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
                - Otherwise, the object will be serialized and uploaded as an artifact.
        artifact_type : int
            Variant of `_CommonService.ArtifactTypeEnum`.

        """
        if isinstance(artifact, six.string_types):
            artifact = open(artifact, 'rb')

        # log key to ModelDB
        Message = _ExperimentRunService.LogArtifact
        artifact_msg = _CommonService.Artifact(key=key,
                                               path_only=False,
                                               artifact_type=artifact_type)
        msg = Message(id=self.id, artifact=artifact_msg)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logArtifact".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("artifact with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                response.raise_for_status()

        # upload artifact to artifact store
        url = self._get_url_for_artifact(key, "PUT")
        artifact_stream, _ = _artifact_utils.ensure_bytestream(artifact)
        response = requests.put(url, data=artifact_stream)
        response.raise_for_status()

    def _log_artifact_path(self, key, artifact_path, artifact_type):
        """
        Logs the filesystem path of an artifact to this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the artifact.
        artifact_path : str
            Filesystem path of the artifact.
        artifact_type : int
            Variant of `_CommonService.ArtifactTypeEnum`.

        """
        # log key-path to ModelDB
        Message = _ExperimentRunService.LogArtifact
        artifact_msg = _CommonService.Artifact(key=key,
                                               path=artifact_path,
                                               path_only=True,
                                               artifact_type=artifact_type)
        msg = Message(id=self.id, artifact=artifact_msg)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logArtifact".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("artifact with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                response.raise_for_status()

    def _get_artifact(self, key):
        """
        Gets the artifact with name `key` from this Experiment Run.

        If the artifact was originally logged as just a filesystem path, that path will be returned.
        Otherwise, bytes representing the artifact object will be returned.

        Parameters
        ----------
        key : str
            Name of the artifact.

        Returns
        -------
        str or bytes
            Filesystem path or bytes representing the artifact.
        bool
            True if the artifact was only logged as its filesystem path.

        """
        # get key-path from ModelDB
        Message = _ExperimentRunService.GetArtifacts
        msg = Message(id=self.id, key=key)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getArtifacts".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        artifact = {artifact.key: artifact for artifact in response_msg.artifacts}.get(key)
        if artifact is None:
            raise KeyError("no artifact found with key {}".format(key))
        if artifact.path_only:
            return artifact.path, artifact.path_only
        else:
            # download artifact from artifact store
            url = self._get_url_for_artifact(key, "GET")
            response = requests.get(url)
            response.raise_for_status()

            return response.content, artifact.path_only

    def log_tag(self, tag):
        """
        Logs a tag to this Experiment Run.

        Tags are short textual labels used to help identify a run, such as its purpose or its environment.

        Parameters
        ----------
        tag : str
            Tag.

        """
        if not isinstance(tag, six.string_types):
            raise TypeError("`tag` must be a string")

        Message = _ExperimentRunService.AddExperimentRunTags
        msg = Message(id=self.id, tags=[tag])
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/addExperimentRunTags".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        response.raise_for_status()

    def log_tags(self, tags):
        """
        Logs multiple tags to this Experiment Run.

        Parameters
        ----------
        tags : list of str
            Tags.

        """
        if isinstance(tags, six.string_types):
            raise TypeError("`tags` must be an iterable of strings")
        for tag in tags:
            if not isinstance(tag, six.string_types):
                raise TypeError("`tags` must be an iterable of strings")

        Message = _ExperimentRunService.AddExperimentRunTags
        msg = Message(id=self.id, tags=tags)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/addExperimentRunTags".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        response.raise_for_status()

    def get_tags(self):
        """
        Gets all tags from this Experiment Run.

        Returns
        -------
        list of str
            All tags.

        """
        Message = _CommonService.GetTags
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunTags".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.tags

    def log_attribute(self, key, value):
        """
        Logs an attribute to this Experiment Run.

        Attributes are descriptive metadata, such as the team responsible for this model or the
        expected training time.

        Parameters
        ----------
        key : str
            Name of the attribute.
        value : one of {None, bool, float, int, str, list, dict}
            Value of the attribute.

        """
        _utils.validate_flat_key(key)

        attribute = _CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
        msg = _ExperimentRunService.LogAttribute(id=self.id, attribute=attribute)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logAttribute".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("attribute with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                response.raise_for_status()

    def log_attributes(self, attributes):
        """
        Logs potentially multiple attributes to this Experiment Run.

        Parameters
        ----------
        attributes : dict of str to {None, bool, float, int, str, list, dict}
            Attributes.

        """
        # validate all keys first
        for key in six.viewkeys(attributes):
            _utils.validate_flat_key(key)

        # build KeyValues
        attribute_keyvals = []
        for key, value in six.viewitems(attributes):
            attribute_keyvals.append(_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True)))

        msg = _ExperimentRunService.LogAttributes(id=self.id, attributes=attribute_keyvals)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logAttributes".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("some attribute with some input key already exists;"
                                 " consider using observations instead")
            else:
                response.raise_for_status()

    def get_attribute(self, key):
        """
        Gets the attribute with name `key` from this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the attribute.

        Returns
        -------
        one of {None, bool, float, int, str}
            Value of the attribute.

        """
        _utils.validate_flat_key(key)

        Message = _CommonService.GetAttributes
        msg = Message(id=self.id, attribute_keys=[key])
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getAttributes".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        attribute =  _utils.unravel_key_values(response_msg.attributes).get(key)
        if attribute is None:
            raise KeyError("no attribute found with key {}".format(key))
        return attribute

    def get_attributes(self):
        """
        Gets all attributes from this Experiment Run.

        Returns
        -------
        dict of str to {None, bool, float, int, str}
            Names and values of all attributes.

        """
        Message = _CommonService.GetAttributes
        msg = Message(id=self.id, get_all=True)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getAttributes".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_key_values(response_msg.attributes)

    def log_metric(self, key, value):
        """
        Logs a metric to this Experiment Run.

        Metrics are unique performance metadata, such as accuracy or loss on the full training set.

        If the metadatum of interest might recur, :meth:`.log_observation` should be used instead.

        Parameters
        ----------
        key : str
            Name of the metric.
        value : one of {None, bool, float, int, str}
            Value of the metric.

        """
        _utils.validate_flat_key(key)

        metric = _CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value))
        msg = _ExperimentRunService.LogMetric(id=self.id, metric=metric)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logMetric".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("metric with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                response.raise_for_status()

    def log_metrics(self, metrics):
        """
        Logs potentially multiple metrics to this Experiment Run.

        Parameters
        ----------
        metrics : dict of str to {None, bool, float, int, str}
            Metrics.

        """
        # validate all keys first
        for key in six.viewkeys(metrics):
            _utils.validate_flat_key(key)

        # build KeyValues
        metric_keyvals = []
        for key, value in six.viewitems(metrics):
            metric_keyvals.append(_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value)))

        msg = _ExperimentRunService.LogMetrics(id=self.id, metrics=metric_keyvals)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logMetrics".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("some metric with some input key already exists;"
                                 " consider using observations instead")
            else:
                response.raise_for_status()

    def get_metric(self, key):
        """
        Gets the metric with name `key` from this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the metric.

        Returns
        -------
        one of {None, bool, float, int, str}
            Value of the metric.

        """
        _utils.validate_flat_key(key)

        Message = _ExperimentRunService.GetMetrics
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getMetrics".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        metric = _utils.unravel_key_values(response_msg.metrics).get(key)
        if metric is None:
            raise KeyError("no metric found with key {}".format(key))
        return metric

    def get_metrics(self):
        """
        Gets all metrics from this Experiment Run.

        Returns
        -------
        dict of str to {None, bool, float, int, str}
            Names and values of all metrics.

        """
        Message = _ExperimentRunService.GetMetrics
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getMetrics".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_key_values(response_msg.metrics)

    def log_hyperparameter(self, key, value):
        """
        Logs a hyperparameter to this Experiment Run.

        Hyperparameters are model configuration metadata, such as the loss function or the
        regularization penalty.

        Parameters
        ----------
        key : str
            Name of the hyperparameter.
        value : one of {None, bool, float, int, str}
            Value of the hyperparameter.

        """
        _utils.validate_flat_key(key)

        hyperparameter = _CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value))
        msg = _ExperimentRunService.LogHyperparameter(id=self.id, hyperparameter=hyperparameter)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logHyperparameter".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("hyperparameter with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                response.raise_for_status()

    def log_hyperparameters(self, hyperparams):
        """
        Logs potentially multiple hyperparameters to this Experiment Run.

        Parameters
        ----------
        hyperparameters : dict of str to {None, bool, float, int, str}
            Hyperparameters.

        """
        # validate all keys first
        for key in six.viewkeys(hyperparams):
            _utils.validate_flat_key(key)

        # build KeyValues
        hyperparameter_keyvals = []
        for key, value in six.viewitems(hyperparams):
            hyperparameter_keyvals.append(_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value)))

        msg = _ExperimentRunService.LogHyperparameters(id=self.id, hyperparameters=hyperparameter_keyvals)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logHyperparameters".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("some hyperparameter with some input key already exists;"
                                 " consider using observations instead")
            else:
                response.raise_for_status()

    def get_hyperparameter(self, key):
        """
        Gets the hyperparameter with name `key` from this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the hyperparameter.

        Returns
        -------
        one of {None, bool, float, int, str}
            Value of the hyperparameter.

        """
        _utils.validate_flat_key(key)

        Message = _ExperimentRunService.GetHyperparameters
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getHyperparameters".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        hyperparameter = _utils.unravel_key_values(response_msg.hyperparameters).get(key)
        if hyperparameter is None:
            raise KeyError("no hyperparameter found with key {}".format(key))
        return hyperparameter

    def get_hyperparameters(self):
        """
        Gets all hyperparameters from this Experiment Run.

        Returns
        -------
        dict of str to {None, bool, float, int, str}
            Names and values of all hyperparameters.

        """
        Message = _ExperimentRunService.GetHyperparameters
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getHyperparameters".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_key_values(response_msg.hyperparameters)

    def log_dataset(self, key, dataset):
        """
        Logs a dataset artifact to this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the dataset.
        dataset : str or file-like or object
            Dataset or some representation thereof.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
                - Otherwise, the object will be serialized and uploaded as an artifact.

        """
        _utils.validate_flat_key(key)

        self._log_artifact(key, dataset, _CommonService.ArtifactTypeEnum.DATA)

    def log_dataset_path(self, key, dataset_path):
        """
        Logs the filesystem path of an dataset to this Experiment Run.

        This function makes no attempt to open a file at `dataset_path`. Only the path string itself
        is logged.

        Parameters
        ----------
        key : str
            Name of the dataset.
        dataset_path : str
            Filesystem path of the dataset.

        """
        _utils.validate_flat_key(key)

        self._log_artifact_path(key, dataset_path, _CommonService.ArtifactTypeEnum.DATA)

    def get_dataset(self, key):
        """
        Gets the dataset artifact with name `key` from this Experiment Run.

        If the dataset was originally logged as just a filesystem path, that path will be returned.
        Otherwise, the dataset object itself will be returned. If the object is unable to be
        deserialized, the raw bytes are returned instead.

        Parameters
        ----------
        key : str
            Name of the dataset.

        Returns
        -------
        str or object or file-like
            Filesystem path of the dataset, the dataset object, or a bytestream representing the
            dataset.

        """
        _utils.validate_flat_key(key)

        dataset, path_only = self._get_artifact(key)
        if path_only:
            return dataset
        else:
            try:
                return pickle.loads(dataset)
            except pickle.UnpicklingError:
                return six.BytesIO(dataset)

    def log_model_for_deployment(self, model, model_api, requirements, train_features=None, train_targets=None):
        """
        Logs a model artifact, a model API, requirements, and a dataset CSV to deploy on Verta.

        Parameters
        ----------
        model : str or file-like or object
            Model or some representation thereof.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
                - Otherwise, the object will be serialized and uploaded as an artifact.
        model_api : str or file-like
            Model API, specifying model deployment and predictions.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
        requirements : str or file-like
            pip requirements file specifying packages necessary to deploy the model.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
        train_features : pd.DataFrame, optional
            pandas DataFrame representing features of the training data. If provided, `train_targets`
            must also be provided.
        train_targets : pd.DataFrame, optional
            pandas DataFrame representing targets of the training data. If provided, `train_features`
            must also be provided.

        Warnings
        --------
        Due to the way deployment currently works, `train_features` and `train_targets` will be joined
        together and then converted into a CSV. Retrieving the dataset through the Client will return
        a file-like bytestream of this CSV that can be passed directly into `pd.read_csv()
        <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html>`_.

        """
        if sum(arg is None for arg in (train_features, train_targets)) == 1:
            raise ValueError("`train_features` and `train_targets` must be provided together")

        # open files
        if isinstance(model, six.string_types):
            model = open(model, 'rb')
        if isinstance(model_api, six.string_types):
            model_api = open(model_api, 'rb')
        if isinstance(requirements, six.string_types):
            requirements = open(requirements, 'rb')

        # prehandle model
        _artifact_utils.reset_stream(model)  # reset cursor to beginning in case user forgot
        model, method, model_type = _artifact_utils.serialize_model(model)
        if method is None:
            raise ValueError("will not be able to deploy model due to unknown serialization method")

        # prehandle model_api
        _artifact_utils.reset_stream(model_api)  # reset cursor to beginning in case user forgot
        model_api = utils.ModelAPI.from_file(model_api)
        if 'model_packaging' not in model_api:
            # add model serialization info to model_api
            model_api['model_packaging'] = {
                'python_version': _utils.get_python_version(),
                'type': model_type,
                'deserialization': method,
            }

        # prehandle requirements
        _artifact_utils.reset_stream(requirements)  # reset cursor to beginning in case user forgot
        _artifact_utils.validate_requirements_txt(requirements)
        if method == "cloudpickle":  # if cloudpickle used, add to requirements
            cloudpickle_dep = "cloudpickle=={}".format(_artifact_utils.cloudpickle.__version__)
            req_deps = six.ensure_str(requirements.read()).splitlines()
            _artifact_utils.reset_stream(requirements)  # reset cursor to beginning as a courtesy
            for req_dep in req_deps:
                if req_dep.startswith("cloudpickle"):  # if present, check version
                    our_ver = cloudpickle_dep.lstrip("cloudpickle==")
                    their_ver = req_dep.lstrip("cloudpickle==")
                    if our_ver != their_ver:  # versions conflict, so raise exception
                        raise ValueError("Client is running with cloudpickle v{}, but the provided requirements specify v{}; "
                                         "these must match".format(our_ver, their_ver))
                    else:  # versions match, so proceed
                        break
            else:  # if not present, add
                req_deps.append(cloudpickle_dep)

            # recreate stream
            requirements = six.BytesIO(six.ensure_binary('\n'.join(req_deps)))

        # prehandle train_features and train_targets
        if train_features is not None and train_targets is not None:
            stringstream = six.StringIO()
            train_df = train_features.join(train_targets)
            train_df.to_csv(stringstream, index=False)  # write as CSV
            stringstream.seek(0)
            train_data = stringstream
        else:
            train_data = None

        self._log_artifact("model.pkl", model, _CommonService.ArtifactTypeEnum.MODEL)
        self._log_artifact("model_api.json", model_api, _CommonService.ArtifactTypeEnum.BLOB)
        self._log_artifact("requirements.txt", requirements, _CommonService.ArtifactTypeEnum.BLOB)
        if train_data is not None:
            self._log_artifact("train_data", train_data, _CommonService.ArtifactTypeEnum.DATA)


    def log_model(self, key, model):
        """
        Logs a model artifact to this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the model.
        model : str or file-like or object
            Model or some representation thereof.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
                - Otherwise, the object will be serialized and uploaded as an artifact.

        """
        _utils.validate_flat_key(key)

        model, _, _ = _artifact_utils.serialize_model(model)

        self._log_artifact(key, model, _CommonService.ArtifactTypeEnum.MODEL)

    def log_model_path(self, key, model_path):
        """
        Logs the filesystem path of an model to this Experiment Run.

        This function makes no attempt to open a file at `model_path`. Only the path string itself
        is logged.

        Parameters
        ----------
        key : str
            Name of the model.
        model_path : str
            Filesystem path of the model.

        """
        _utils.validate_flat_key(key)

        self._log_artifact_path(key, model_path, _CommonService.ArtifactTypeEnum.MODEL)

    def get_model(self, key):
        """
        Gets the model artifact with name `key` from this Experiment Run.

        If the model was originally logged as just a filesystem path, that path will be returned.
        Otherwise, the model object itself will be returned. If the object is unable to be
        deserialized, the raw bytes are returned instead.

        Parameters
        ----------
        key : str
            Name of the model.

        Returns
        -------
        str or object or file-like
            Filesystem path of the model, the model object, or a bytestream representing the model.

        """
        _utils.validate_flat_key(key)

        model, path_only = self._get_artifact(key)
        if path_only:
            return model
        else:
            return _artifact_utils.deserialize_model(model)

    def log_image(self, key, image):
        """
        Logs a image artifact to this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the image.
        image : one of {str, file-like, pyplot, matplotlib Figure, PIL Image, object}
            Image or some representation thereof.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
                - If matplotlib pyplot, then the image will be serialized and uploaded as an artifact.
                - If matplotlib Figure, then the image will be serialized and uploaded as an artifact.
                - If PIL Image, then the image will be serialized and uploaded as an artifact.
                - Otherwise, the object will be serialized and uploaded as an artifact.

        """
        _utils.validate_flat_key(key)

        # convert pyplot, Figure or Image to bytestream
        bytestream = six.BytesIO()
        try:  # handle matplotlib
            image.savefig(bytestream)
        except AttributeError:
            try:  # handle PIL Image
                colors = image.getcolors()
            except AttributeError:
                pass
            else:
                if len(colors) == 1 and all(val == 255 for val in colors[0][1]):
                    warnings.warn("the image being logged is blank")
                image.save(bytestream, 'png')

        bytestream.seek(0)
        if bytestream.read(1):
            bytestream.seek(0)
            image = bytestream

        self._log_artifact(key, image, _CommonService.ArtifactTypeEnum.IMAGE)

    def log_image_path(self, key, image_path):
        """
        Logs the filesystem path of an image to this Experiment Run.

        This function makes no attempt to open a file at `image_path`. Only the path string itself
        is logged.

        Parameters
        ----------
        key : str
            Name of the image.
        image_path : str
            Filesystem path of the image.

        """
        _utils.validate_flat_key(key)

        self._log_artifact_path(key, image_path, _CommonService.ArtifactTypeEnum.IMAGE)

    def get_image(self, key):
        """
        Gets the image artifact with name `key` from this Experiment Run.

        If the image was originally logged as just a filesystem path, that path will be returned.
        Otherwise, the image object will be returned. If the object is unable to be deserialized,
        the raw bytes are returned instead.

        Parameters
        ----------
        key : str
            Name of the image.

        Returns
        -------
        str or PIL Image or file-like
            Filesystem path of the image, the image object, or a bytestream representing the image.

        """
        _utils.validate_flat_key(key)

        image, path_only = self._get_artifact(key)
        if path_only:
            return image
        else:
            try:
                return PIL.Image.open(six.BytesIO(image))
            except IOError:
                return six.BytesIO(image)

    def log_artifact(self, key, artifact):
        """
        Logs an artifact to this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the artifact.
        artifact : str or file-like or object
            Artifact or some representation thereof.
                - If str, then it will be interpreted as a filesystem path, its contents read as bytes,
                  and uploaded as an artifact.
                - If file-like, then the contents will be read as bytes and uploaded as an artifact.
                - Otherwise, the object will be serialized and uploaded as an artifact.

        """
        _utils.validate_flat_key(key)

        self._log_artifact(key, artifact, _CommonService.ArtifactTypeEnum.BLOB)

    def log_artifact_path(self, key, artifact_path):
        """
        Logs the filesystem path of an artifact to this Experiment Run.

        This function makes no attempt to open a file at `artifact_path`. Only the path string itself
        is logged.

        Parameters
        ----------
        key : str
            Name of the artifact.
        artifact_path : str
            Filesystem path of the artifact.

        """
        _utils.validate_flat_key(key)

        self._log_artifact_path(key, artifact_path, _CommonService.ArtifactTypeEnum.BLOB)

    def get_artifact(self, key):
        """
        Gets the artifact with name `key` from this Experiment Run.

        If the artifact was originally logged as just a filesystem path, that path will be returned.
        Otherwise, the artifact object will be returned. If the object is unable to be deserialized,
        the raw bytes are returned instead.

        Parameters
        ----------
        key : str
            Name of the artifact.

        Returns
        -------
        str or bytes
            Filesystem path of the artifact, the artifact object, or a bytestream representing the
            artifact.

        """
        _utils.validate_flat_key(key)

        artifact, path_only = self._get_artifact(key)
        if path_only:
            return artifact
        else:
            try:
                return pickle.loads(artifact)
            except pickle.UnpicklingError:
                return six.BytesIO(artifact)

    def log_observation(self, key, value, timestamp=None):
        """
        Logs an observation to this Experiment Run.

        Observations are recurring metadata that are repeatedly measured over time, such as batch
        losses over an epoch or memory usage.

        Parameters
        ----------
        key : str
            Name of the observation.
        value : one of {None, bool, float, int, str}
            Value of the observation.
        timestamp: str or float or int, optional
            String representation of a datetime or numerical Unix timestamp. If not provided, the
            current time will be used.

        Warnings
        --------
        If `timestamp` is provided by the user, it must contain timezone information. Otherwise,
        it will be interpreted as UTC.

        """
        _utils.validate_flat_key(key)

        if timestamp is None:
            timestamp = _utils.now()
        else:
            timestamp = _utils.ensure_timestamp(timestamp)

        attribute = _CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value))
        observation = _ExperimentRunService.Observation(attribute=attribute, timestamp=timestamp)  # TODO: support Artifacts
        msg = _ExperimentRunService.LogObservation(id=self.id, observation=observation)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logObservation".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       json=data)
        response.raise_for_status()

    def get_observation(self, key):
        """
        Gets the observation series with name `key` from this Experiment Run.

        Parameters
        ----------
        key : str
            Name of observation series.

        Returns
        -------
        list of {None, bool, float, int, str}
            Values of observation series.

        """
        _utils.validate_flat_key(key)

        Message = _ExperimentRunService.GetObservations
        msg = Message(id=self.id, observation_key=key)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getObservations".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if len(response_msg.observations) == 0:
            raise KeyError(key)
        else:
            return [_utils.unravel_observation(observation)[1:]  # drop key from tuple
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
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunById".format(self._scheme, self._socket),
                                       self._auth, self._retry,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_observations(response_msg.experiment_run.observations)

    def log_code(self, file=None, git_sha=None, remote_url=None):
        """
        Logs a code version to this Experiment Run.

        A code version consists of a group of artifacts and attributes that describe the state of code.

        Parameters
        ----------
        file : str or file-like, optional
            Python script or Jupyter notebook file. If no file is provided, the Client will make its
            best effort to dynamically find the script/notebook file that is calling this function.
        git_sha : str, optional
        remote_utl : str, optional

        """
        if isinstance(file, six.string_types):
            file = open(file, 'r')
        elif file is None:
            try:
                filename = _utils.get_notebook_filepath()
            except OSError:  # notebook not found
                try:
                    filename = _utils.get_script_filepath()
                except OSError:  # script not found
                    print("unable to find code file; skipping")
                else:
                    print("reading code from {}".format(filename))
                    file = open(filename, 'r')
            else:
                print("reading code from {}".format(filename))
                file = open(filename, 'r')
