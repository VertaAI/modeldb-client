# -*- coding: utf-8 -*-

import six
import six.moves.cPickle as pickle
from six.moves.urllib.parse import urlparse

import ast
import hashlib
import importlib
import os
import pprint
import re
import sys
import time
import warnings
import zipfile

import requests

try:
    import PIL
except ImportError:  # Pillow not installed
    PIL = None

from ._protos.public.modeldb import CommonService_pb2 as _CommonService
from ._protos.public.modeldb import ProjectService_pb2 as _ProjectService
from ._protos.public.modeldb import ExperimentService_pb2 as _ExperimentService
from ._protos.public.modeldb import ExperimentRunService_pb2 as _ExperimentRunService
from . import __about__
from . import _dataset
from . import _utils
from . import _artifact_utils
from . import utils


_GRPC_PREFIX = "Grpc-Metadata-"


class Client(object):
    """
    Object for interfacing with the ModelDB backend.

    .. deprecated:: 0.12.0
       The `port` parameter will removed in v0.14.0; please combine `port` with the first parameter,
       e.g. `Client("localhost:8080")`.
    .. deprecated:: 0.13.3
       The `expt_runs` attribute will removed in v0.14.0; consider using `proj.expt_runs` and
       `expt.expt_runs` instead.

    This class provides functionality for starting/resuming Projects, Experiments, and Experiment Runs.

    Parameters
    ----------
    host : str
        Hostname of the Verta Web App.
    email : str, optional
        Authentication credentials for managed service. If this does not sound familiar, then there
        is no need to set it.
    dev_key : str, optional
        Authentication credentials for managed service. If this does not sound familiar, then there
        is no need to set it.
    max_retries : int, default 5
        Maximum number of times to retry a request on a connection failure. This only attempts retries
        on HTTP codes {403, 503, 504} which commonly occur during back end connection lapses.
    ignore_conn_err : bool, default False
        Whether to ignore connection errors and instead return successes with empty contents.
    use_git : bool, default True
        Whether to use a local Git repository for certain operations such as Code Versioning.
    debug : bool, default False
        Whether to print extra verbose information to aid in debugging.

    Attributes
    ----------
    max_retries : int
        Maximum number of times to retry a request on a connection failure. Changes to this value
        propagate to any objects that are/were created from this Client.
    ignore_conn_err : bool
        Whether to ignore connection errors and instead return successes with empty contents. Changes
        to this value propagate to any objects that are/were created from this Client.
    debug : bool
        Whether to print extra verbose information to aid in debugging. Changes to this value propagate
        to any objects that are/were created from this Client.
    proj : :class:`Project` or None
        Currently active Project.
    expt : :class:`Experiment` or None
        Currently active Experiment.

    """
    def __init__(self, host, port=None, email=None, dev_key=None,
                 max_retries=5, ignore_conn_err=False, use_git=True, debug=False):
        if email is None and 'VERTA_EMAIL' in os.environ:
            email = os.environ['VERTA_EMAIL']
            print("set email from environment")
        if dev_key is None and 'VERTA_DEV_KEY' in os.environ:
            dev_key = os.environ['VERTA_DEV_KEY']
            print("set developer key from environment")

        scheme = auth = None
        if email is None and dev_key is None:
            if debug:
                print("[DEBUG] email and developer key not found; auth disabled")
            auth = None
            scheme = "http"
        elif email is not None and dev_key is not None:
            if debug:
                print("[DEBUG] using email: {}".format(email))
                print("[DEBUG] using developer key: {}".format(dev_key[:8] + re.sub(r"[^-]", '*', dev_key[8:])))
            auth = {_GRPC_PREFIX+'email': email,
                    _GRPC_PREFIX+'developer_key': dev_key,
                    _GRPC_PREFIX+'source': "PythonClient"}
            scheme = "https"
            # save credentials to env for other Verta Client features
            os.environ['VERTA_EMAIL'] = email
            os.environ['VERTA_DEV_KEY'] = dev_key
        else:
            raise ValueError("`email` and `dev_key` must be provided together")

        back_end_url = urlparse(host)
        scheme = back_end_url.scheme or scheme
        socket = back_end_url.netloc + back_end_url.path.rstrip('/')
        if port is not None:
            warnings.warn("`port` (the second parameter) will removed in a later version;"
                          " please combine it with the first parameter, e.g. \"localhost:8080\"",
                          category=FutureWarning)
            socket = "{}:{}".format(socket, port)

        # verify connection
        conn = _utils.Connection(scheme, socket, auth, max_retries, ignore_conn_err)
        try:
            response = _utils.make_request("GET",
                                           "{}://{}/v1/project/verifyConnection".format(conn.scheme, conn.socket),
                                           conn)
        except requests.ConnectionError:
            six.raise_from(requests.ConnectionError("connection failed; please check `host` and `port`"),
                           None)

        def is_unauthorized(response): return response.status_code == 401

        if is_unauthorized(response):
            auth_error_msg = "authentication failed; please check `VERTA_EMAIL` and `VERTA_DEV_KEY`"
            six.raise_from(requests.HTTPError(auth_error_msg), None)

        _utils.raise_for_http_error(response)
        print("connection successfully established")

        self._conn = conn
        self._conf = _utils.Configuration(use_git, debug)

        self.proj = None
        self.expt = None

    @property
    def max_retries(self):
        return self._conn.retry.total

    @max_retries.setter
    def max_retries(self, value):
        self._conn.retry.total = value

    @property
    def ignore_conn_err(self):
        return self._conn.ignore_conn_err

    @ignore_conn_err.setter
    def ignore_conn_err(self, value):
        self._conn.ignore_conn_err = value

    @property
    def use_git(self):
        return self._conf.use_git

    @use_git.setter
    def use_git(self, _):
        """This would mess with state in safe but unexpected ways."""
        raise AttributeError("cannot set `use_git` after Client has been initialized")

    @property
    def debug(self):
        return self._conf.debug

    @debug.setter
    def debug(self, value):
        self._conf.debug = value

    @property
    def expt_runs(self):
        warnings.warn("`client.expt_runs` is deprecated and will removed in a later version;"
                      " consider using `proj.expt_runs` and `expt.expt_runs` instead",
                      category=FutureWarning)

        if self.expt is None:
            return None
        else:
            Message = _ExperimentRunService.GetExperimentRunsInProject
            msg = Message(project_id=self.proj.id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment-run/getExperimentRunsInProject".format(self._conn.scheme, self._conn.socket),
                                           self._conn, params=data)
            _utils.raise_for_http_error(response)

            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            expt_run_ids = [expt_run.id
                            for expt_run in response_msg.experiment_runs
                            if expt_run.experiment_id == self.expt.id]
            return ExperimentRuns(self._conn, self._conf, expt_run_ids)

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

        self.proj = Project(self._conn, self._conf,
                            name,
                            desc, tags, attrs,
                            id)

        return self.proj

    def set_experiment(self, name=None, desc=None, tags=None, attrs=None, id=None):
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
        if name is not None and id is not None:
            raise ValueError("cannot specify both `name` and `id`")
        elif id is not None:
            # find Experiment by ID
            expt_msg = Experiment._get(self._conn, _expt_id=id)
            if expt_msg is None:
                raise ValueError("no Experiment found with ID {}".format(id))
            # set parent Project by ID
            try:
                self.proj = Project(self._conn, self._conf, _proj_id=expt_msg.project_id)
            except ValueError:  # parent Project not found
                raise RuntimeError("unable to find parent Project of Experiment with ID {};"
                                   " this should only ever occur due to a back end error".format(id))
            # set Experiment
            self.expt = Experiment(self._conn, self._conf,
                                   _expt_id=id)
        else:
            # set Experiment by name under current Project
            if self.proj is None:
                raise AttributeError("a Project must first be in progress")
            self.expt = Experiment(self._conn, self._conf,
                                   self.proj.id, name,
                                   desc, tags, attrs)

        return self.expt

    def set_experiment_run(self, name=None, desc=None, tags=None, attrs=None, id=None):
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
        if name is not None and id is not None:
            raise ValueError("cannot specify both `name` and `id`")
        elif id is not None:
            # find ExperimentRun by ID
            expt_run_msg = ExperimentRun._get(self._conn, _expt_run_id=id)
            if expt_run_msg is None:
                raise ValueError("no ExperimentRun found with ID {}".format(id))
            # set parent Project by ID
            try:
                self.proj = Project(self._conn, self._conf, _proj_id=expt_run_msg.project_id)
            except ValueError:  # parent Project not found
                raise RuntimeError("unable to find parent Project of ExperimentRun with ID {};"
                                   " this should only ever occur due to a back end error".format(id))
            # set parent Experiment by ID
            try:
                self.expt = Experiment(self._conn, self._conf, _expt_id=expt_run_msg.experiment_id)
            except ValueError:  # parent Experiment not found
                raise RuntimeError("unable to find parent Experiment of ExperimentRun with ID {};"
                                   " this should only ever occur due to a back end error".format(id))
            # set ExperimentRun
            expt_run = ExperimentRun(self._conn, self._conf,
                                     _expt_run_id=id)
        else:
            # set ExperimentRun by name under current Experiment
            if self.expt is None:
                raise AttributeError("an Experiment must first be in progress")
            expt_run = ExperimentRun(self._conn, self._conf,
                                     self.proj.id, self.expt.id, name,
                                     desc, tags, attrs)

        return expt_run

    # NOTE: dataset visibility cannot be set via a client
    def set_dataset(self, name=None, type="local",
                    desc=None, tags=None, attrs=None,
                    id=None):
        """
        Attaches a Dataset to this Client.

        If an accessible Dataset with name `name` does not already exist, it will be created
        and initialized with specified metadata parameters. If such a Dataset does already exist,
        it will be retrieved; specifying metadata parameters in this case will raise an exception.

        Parameters
        ----------
        name : str, optional
            Name of the Dataset. If no name is provided, one will be generated.
        type : str, one of {'local', 's3', 'big query', 'atlas hive', 'postgres'}
            The type of the dataset so we can collect the right type of metadata
        desc : str, optional
            Description of the Dataset.
        tags : list of str, optional
            Tags of the Dataset.
        attrs : dict of str to {None, bool, float, int, str}, optional
            Attributes of the Dataset.
        id : str
            ID of the Dataset. This parameter cannot be provided alongside `name`, and other
            parameters will be ignored.

        Returns
        -------
        :class:`Dataset`

        Raises
        ------
        ValueError
            If a Dataset with `name` already exists, but metadata parameters are passed in.

        """
        # Note: If a dataset with `name` already exists,
        #       there is no way to determine its type/subclass from back end,
        #       so it is assumed that the user has passed in the correct `type`.
        if type == "local":
            DatasetSubclass = _dataset.LocalDataset
        elif type == "s3":
            DatasetSubclass = _dataset.S3Dataset
        elif type == "big query":
            DatasetSubclass = _dataset.BigQueryDataset
        elif type == "atlas hive":
            DatasetSubclass = _dataset.AtlasHiveDataset
        elif type == "postgres":
            DatasetSubclass = _dataset.RDBMSDataset
        else:
            raise ValueError("`type` must be one of {'local', 's3', 'big query', 'atlas hive', 'postgres'}")

        return DatasetSubclass(self._conn, self._conf,
                               name=name, desc=desc, tags=tags, attrs=attrs,
                               _dataset_id=id)

    def get_dataset(self, name=None, id=None):
        """
        Retrieve an already created Dataset. Only one of name or id can be provided.

        Parameters
        ----------
        name : str, optional
            Name of the Dataset.
        id : str, optional
            ID of the Dataset. This parameter cannot be provided alongside `name`.

        Returns
        -------
        :class:`Dataset`
        """
        return _dataset.Dataset(self._conn, self._conf, name=name, _dataset_id=id)

    def find_datasets(self,
                      dataset_ids=None, name=None,
                      tags=None,
                      sort_key=None, ascending=False):
        """
        Gets the Datasets that match the given query parameters. If no parameters
        are specified, we return all datasets.

        Parameters
        ----------
        dataset_ids : list of str, optional
            IDs of datasets that we wish to retrieve
        name: str, optional
            Name of dataset we wish to retrieve. Fuzzy matches supported
        tags: list of str, optional
            List of tags by which we'd like to query datasets
        sort_key: string, optional
            Key by which the resulting list of datasets should be sorted
        ascending: bool, default: False
            Whether to sort returned datasets in ascending or descending order

        Returns
        -------
        list of :class:`Dataset`

        """
        predicates = []
        if tags is not None:
            for tag in tags:
                predicates.append(
                    _CommonService.KeyValueQuery(key="tags",
                                                 value=_utils.python_to_val_proto(tag),
                                                 operator=_CommonService.OperatorEnum.EQ))
        if name is not None:
            predicates.append(
                _CommonService.KeyValueQuery(key="name",
                                             value=_utils.python_to_val_proto(name),
                                             operator=_CommonService.OperatorEnum.EQ))
        Message = _dataset._DatasetService.FindDatasets
        msg = Message(dataset_ids=dataset_ids, predicates=predicates,
                      ascending=ascending, sort_key=sort_key)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/dataset/findDatasets".format(
                                           self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return [_dataset.Dataset(self._conn, self._conf, _dataset_id=dataset.id)
                for dataset in response_msg.datasets]

    def get_dataset_version(self, id):
        """
        Retrieve an already created DatasetVersion.

        Parameters
        ----------
        id : str
            ID of the DatasetVersion.

        Returns
        -------
        :class:`DatasetVersion`
        """
        return _dataset.DatasetVersion(self._conn, self._conf, _dataset_version_id=id)


class _ModelDBEntity(object):
    def __init__(self, conn, conf, service_module, service_url_component, id):
        self._conn = conn
        self._conf = conf

        self._service = service_module
        self._request_url = "{}://{}/v1/{}/{}".format(self._conn.scheme,
                                                      self._conn.socket,
                                                      service_url_component,
                                                      '{}')  # endpoint placeholder

        self.id = id

    def __getstate__(self):
        state = self.__dict__.copy()

        state['_service_module_name'] = state['_service'].__name__
        del state['_service']

        return state

    def __setstate__(self, state):
        state['_service'] = importlib.import_module(state['_service_module_name'])
        del state['_service_module_name']

        self.__dict__.update(state)

    def _get_url_for_artifact(self, key, method, artifact_type=0):
        """
        Obtains a URL to use for accessing stored artifacts.

        Parameters
        ----------
        key : str
            Name of the artifact.
        method : {'GET', 'PUT'}
            HTTP method to request for the generated URL.
        artifact_type : int, optional
            Variant of `_CommonService.ArtifactTypeEnum`. This informs the backend what slot to check
            for the artifact, if necessary.

        Returns
        -------
        str
            Generated URL.

        """
        if method.upper() not in ("GET", "PUT"):
            raise ValueError("`method` must be one of {'GET', 'PUT'}")

        Message = _CommonService.GetUrlForArtifact
        msg = Message(id=self.id, key=key, method=method.upper(), artifact_type=artifact_type)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       self._request_url.format("getUrlForArtifact"),
                                       self._conn, json=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.url

    def log_code(self, exec_path=None, repo_url=None, commit_hash=None):
        """
        Logs the code version.

        A code version is either information about a Git snapshot or a bundle of Python source code files.

        `repo_url` and `commit_hash` can only be set if `use_git` was set to ``True`` in the Client.

        Parameters
        ----------
        exec_path : str, optional
            Filepath to the executable Python script or Jupyter notebook. If no filepath is provided,
            the Client will make its best effort to find the currently running script/notebook file.
        repo_url : str, optional
            URL for a remote Git repository containing `commit_hash`. If no URL is provided, the Client
            will make its best effort to find it.
        commit_hash : str, optional
            Git commit hash associated with this code version. If no hash is provided, the Client will
            make its best effort to find it.

        Examples
        --------
        With ``Client(use_git=True)`` (default):

            Log Git snapshot information, plus the location of the currently executing notebook/script
            relative to the repository root:

            >>> proj.log_code()
            >>> proj.get_code()
            {'exec_path': 'comparison/outcomes/classification.ipynb',
            'repo_url': 'git@github.com:VertaAI/experiments.git',
            'commit_hash': 'f99abcfae6c3ce6d22597f95ad6ef260d31527a6',
            'is_dirty': False}

            Log Git snapshot information, plus the location of a specific source code file relative
            to the repository root:

            >>> proj.log_code("../trainer/training_pipeline.py")
            >>> proj.get_code()
            {'exec_path': 'comparison/trainer/training_pipeline.py',
            'repo_url': 'git@github.com:VertaAI/experiments.git',
            'commit_hash': 'f99abcfae6c3ce6d22597f95ad6ef260d31527a6',
            'is_dirty': False}

        With ``Client(use_git=False)``:

            Find and upload the currently executing notebook/script:

            >>> proj.log_code()
            >>> zip_file = proj.get_code()
            >>> zip_file.printdir()
            File Name                          Modified             Size
            classification.ipynb        2019-07-10 17:18:24        10287

            Upload a specific source code file:

            >>> proj.log_code("../trainer/training_pipeline.py")
            >>> zip_file = proj.get_code()
            >>> zip_file.printdir()
            File Name                          Modified             Size
            training_pipeline.py        2019-05-31 10:34:44          964

        """
        if self._conf.use_git:
            # verify Git
            try:
                repo_root_dir = _utils.get_git_repo_root_dir()
            except OSError:
                six.raise_from(OSError("failed to locate Git repository; please check your working directory"),
                               None)
            print("Git repository successfully located at {}".format(repo_root_dir))
        elif repo_url is not None or commit_hash is not None:
            raise ValueError("`repo_url` and `commit_hash` can only be set if `use_git` was set to True in the Client")

        if exec_path is None:
            # find dynamically
            try:
                exec_path = _utils.get_notebook_filepath()
            except OSError:  # notebook not found
                try:
                    exec_path = _utils.get_script_filepath()
                except OSError:  # script not found
                    print("unable to find code file; skipping")
        else:
            if not os.path.isfile(exec_path):
                raise ValueError("`exec_path` \"{}\" must be a valid filepath".format(exec_path))

        if isinstance(self, Project):  # TODO: not this
            Message = self._service.LogProjectCodeVersion
            endpoint = "logProjectCodeVersion"
        elif isinstance(self, Experiment):
            Message = self._service.LogExperimentCodeVersion
            endpoint = "logExperimentCodeVersion"
        elif isinstance(self, ExperimentRun):
            Message = self._service.LogExperimentRunCodeVersion
            endpoint = "logExperimentRunCodeVersion"
        msg = Message(id=self.id)
        if self._conf.use_git:
            try:
                # adjust `exec_path` to be relative to repo root
                exec_path = os.path.relpath(exec_path, _utils.get_git_repo_root_dir())
            except OSError as e:
                print("{}; logging absolute path to file instead")
                exec_path = os.path.abspath(exec_path)
            msg.code_version.git_snapshot.filepaths.append(exec_path)

            try:
                msg.code_version.git_snapshot.repo = repo_url or _utils.get_git_remote_url()
            except OSError as e:
                print("{}; skipping".format(e))

            try:
                msg.code_version.git_snapshot.hash = commit_hash or _utils.get_git_commit_hash()
            except OSError as e:
                print("{}; skipping".format(e))

            try:
                is_dirty = _utils.get_git_commit_dirtiness(commit_hash)
            except OSError as e:
                print("{}; skipping".format(e))
            else:
                msg.code_version.git_snapshot.is_dirty = _CommonService.TernaryEnum.TRUE if is_dirty else _CommonService.TernaryEnum.FALSE
        else:  # log code as Artifact
            # write ZIP archive
            zipstream = six.BytesIO()
            with zipfile.ZipFile(zipstream, 'w') as zipf:
                # TODO: save notebook
                zipf.write(exec_path, os.path.basename(exec_path))  # write as base filename
            zipstream.seek(0)

            key = 'code'
            extension = 'zip'

            artifact_hash = hashlib.sha256(zipstream.read()).hexdigest()
            zipstream.seek(0)
            basename = key + os.extsep + extension
            artifact_path = os.path.join(artifact_hash, basename)

            msg.code_version.code_archive.path = artifact_path
            msg.code_version.code_archive.path_only = False
            msg.code_version.code_archive.artifact_type = _CommonService.ArtifactTypeEnum.CODE
            msg.code_version.code_archive.filename_extension = extension
        # TODO: check if we actually have any loggable information
        msg.code_version.date_logged = _utils.now()

        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       self._request_url.format(endpoint),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("a code version has already been logged")
            else:
                _utils.raise_for_http_error(response)

        if msg.code_version.WhichOneof("code") == 'code_archive':
            # upload artifact to artifact store
            url = self._get_url_for_artifact("verta_code_archive", "PUT", msg.code_version.code_archive.artifact_type)
            response = _utils.make_request("PUT", url, self._conn, data=zipstream)
            _utils.raise_for_http_error(response)

    def get_code(self):
        """
        Gets the code version.

        Returns
        -------
        dict or zipfile.ZipFile
            Either:
                - a dictionary containing Git snapshot information with at most the following items:
                    - **filepaths** (*list of str*)
                    - **repo** (*str*) – Remote repository URL
                    - **hash** (*str*) – Commit hash
                    - **is_dirty** (*bool*)
                - a `ZipFile <https://docs.python.org/3/library/zipfile.html#zipfile.ZipFile>`_
                  containing Python source code files

        """
        if isinstance(self, Project):  # TODO: not this
            Message = self._service.GetProjectCodeVersion
            endpoint = "getProjectCodeVersion"
        elif isinstance(self, Experiment):
            Message = self._service.GetExperimentCodeVersion
            endpoint = "getExperimentCodeVersion"
        elif isinstance(self, ExperimentRun):
            Message = self._service.GetExperimentRunCodeVersion
            endpoint = "getExperimentRunCodeVersion"
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       self._request_url.format(endpoint),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        code_ver_msg = response_msg.code_version
        which_code = code_ver_msg.WhichOneof('code')
        if which_code == 'git_snapshot':
            git_snapshot_msg = code_ver_msg.git_snapshot
            git_snapshot = {}
            if git_snapshot_msg.filepaths:
                git_snapshot['filepaths'] = git_snapshot_msg.filepaths
            if git_snapshot_msg.repo:
                git_snapshot['repo_url'] = git_snapshot_msg.repo
            if git_snapshot_msg.hash:
                git_snapshot['commit_hash'] = git_snapshot_msg.hash
                if git_snapshot_msg.is_dirty != _CommonService.TernaryEnum.UNKNOWN:
                    git_snapshot['is_dirty'] = git_snapshot_msg.is_dirty == _CommonService.TernaryEnum.TRUE
            return git_snapshot
        elif which_code == 'code_archive':
            # download artifact from artifact store
            url = self._get_url_for_artifact("verta_code_archive", "GET", code_ver_msg.code_archive.artifact_type)
            response = _utils.make_request("GET", url, self._conn)
            _utils.raise_for_http_error(response)

            code_archive = six.BytesIO(response.content)
            return zipfile.ZipFile(code_archive, 'r')  # TODO: return a util class instead, maybe
        else:
            raise RuntimeError("unable find code in response")


class Project(_ModelDBEntity):
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
    def __init__(self, conn, conf,
                 proj_name=None,
                 desc=None, tags=None, attrs=None,
                 _proj_id=None):
        if proj_name is not None and _proj_id is not None:
            raise ValueError("cannot specify both `proj_name` and `_proj_id`")

        if _proj_id is not None:
            proj = Project._get(conn, _proj_id=_proj_id)
            if proj is not None:
                print("set existing Project: {}".format(proj.name))
            else:
                raise ValueError("Project with ID {} not found".format(_proj_id))
        else:
            if proj_name is None:
                proj_name = Project._generate_default_name()
            try:
                proj = Project._create(conn, proj_name, desc, tags, attrs)
            except requests.HTTPError as e:
                if e.response.status_code == 409:  # already exists
                    if any(param is not None for param in (desc, tags, attrs)):
                        warnings.warn("Project with name {} already exists;"
                                      " cannot initialize `desc`, `tags`, or `attrs`".format(proj_name))
                    proj = Project._get(conn, proj_name)
                    print("set existing Project: {}".format(proj.name))
                else:
                    raise e
            else:
                print("created new Project: {}".format(proj.name))

        super(Project, self).__init__(conn, conf, _ProjectService, "project", proj.id)

    def __repr__(self):
        return "<Project \"{}\">".format(self.name)

    @property
    def name(self):
        Message = _ProjectService.GetProjectById
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/project/getProjectById".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.project.name

    @property
    def expt_runs(self):
        # get runs in this Project
        Message = _ExperimentRunService.GetExperimentRunsInProject
        msg = Message(project_id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunsInProject".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        expt_run_ids = [expt_run.id
                        for expt_run
                        in _utils.json_to_proto(response.json(), Message.Response).experiment_runs]
        return ExperimentRuns(self._conn, self._conf, expt_run_ids)

    @staticmethod
    def _generate_default_name():
        return "Proj {}".format(_utils.generate_default_name())

    @staticmethod
    def _get(conn, proj_name=None, _proj_id=None):
        if _proj_id is not None:
            Message = _ProjectService.GetProjectById
            msg = Message(id=_proj_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/project/getProjectById".format(conn.scheme, conn.socket),
                                           conn, params=data)

            if response.ok:
                response_msg = _utils.json_to_proto(response.json(), Message.Response)
                return response_msg.project
            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    _utils.raise_for_http_error(response)
        elif proj_name is not None:
            Message = _ProjectService.GetProjectByName
            msg = Message(name=proj_name)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/project/getProjectByName".format(conn.scheme, conn.socket),
                                           conn, params=data)

            if response.ok:
                response_msg = _utils.json_to_proto(response.json(), Message.Response)
                return response_msg.project_by_user
            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    _utils.raise_for_http_error(response)
        else:
            raise ValueError("insufficient arguments")

    @staticmethod
    def _create(conn, proj_name, desc=None, tags=None, attrs=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        Message = _ProjectService.CreateProject
        msg = Message(name=proj_name, description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/project/createProject".format(conn.scheme, conn.socket),
                                       conn, json=data)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.project
        else:
            _utils.raise_for_http_error(response)


class Experiment(_ModelDBEntity):
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
    def __init__(self, conn, conf,
                 proj_id=None, expt_name=None,
                 desc=None, tags=None, attrs=None,
                 _expt_id=None):
        if expt_name is not None and _expt_id is not None:
            raise ValueError("cannot specify both `expt_name` and `_expt_id`")

        if _expt_id is not None:
            expt = Experiment._get(conn, _expt_id=_expt_id)
            if expt is not None:
                print("set existing Experiment: {}".format(expt.name))
            else:
                raise ValueError("Experiment with ID {} not found".format(_expt_id))
        elif proj_id is not None:
            if expt_name is None:
                expt_name = Experiment._generate_default_name()
            try:
                expt = Experiment._create(conn, proj_id, expt_name, desc, tags, attrs)
            except requests.HTTPError as e:
                if e.response.status_code == 409:  # already exists
                    if any(param is not None for param in (desc, tags, attrs)):
                        warnings.warn("Experiment with name {} already exists;"
                                      " cannot initialize `desc`, `tags`, or `attrs`".format(expt_name))
                    expt = Experiment._get(conn, proj_id, expt_name)
                    print("set existing Experiment: {}".format(expt.name))
                else:
                    raise e
            else:
                print("created new Experiment: {}".format(expt.name))
        else:
            raise ValueError("insufficient arguments")

        super(Experiment, self).__init__(conn, conf, _ExperimentService, "experiment", expt.id)

    def __repr__(self):
        return "<Experiment \"{}\">".format(self.name)

    @property
    def name(self):
        Message = _ExperimentService.GetExperimentById
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment/getExperimentById".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.experiment.name

    @property
    def expt_runs(self):
        # get runs in this Experiment
        Message = _ExperimentRunService.GetExperimentRunsInExperiment
        msg = Message(experiment_id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunsInExperiment".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        expt_run_ids = [expt_run.id
                        for expt_run
                        in _utils.json_to_proto(response.json(), Message.Response).experiment_runs]
        return ExperimentRuns(self._conn, self._conf, expt_run_ids)

    @staticmethod
    def _generate_default_name():
        return "Expt {}".format(_utils.generate_default_name())

    @staticmethod
    def _get(conn, proj_id=None, expt_name=None, _expt_id=None):
        if _expt_id is not None:
            Message = _ExperimentService.GetExperimentById
            msg = Message(id=_expt_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment/getExperimentById".format(conn.scheme, conn.socket),
                                           conn, params=data)
        elif None not in (proj_id, expt_name):
            Message = _ExperimentService.GetExperimentByName
            msg = Message(project_id=proj_id, name=expt_name)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment/getExperimentByName".format(conn.scheme, conn.socket),
                                           conn, params=data)
        else:
            raise ValueError("insufficient arguments")

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment
        else:
            if response.status_code == 404 and response.json()['code'] == 5:
                return None
            else:
                _utils.raise_for_http_error(response)

    @staticmethod
    def _create(conn, proj_id, expt_name, desc=None, tags=None, attrs=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        Message = _ExperimentService.CreateExperiment
        msg = Message(project_id=proj_id, name=expt_name,
                      description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment/createExperiment".format(conn.scheme, conn.socket),
                                       conn, json=data)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment
        else:
            _utils.raise_for_http_error(response)


class ExperimentRuns(object):
    r"""
    ``list``-like object representing a collection of machine learning Experiment Runs.

    This class provides functionality for filtering and sorting its contents.

    There should not be a need to instantiate this class directly; please use other classes'
    attributes to access Experiment Runs.

    Warnings
    --------
    After an :class:`ExperimentRuns` instance is assigned to a variable, it will be detached from
    the method that created it, and *will never automatically update itself*.

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

    The individual :class:`ExperimentRun`\ s themselves, however, are still synchronized with the
    backend.

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
    _OP_MAP = {'==': _CommonService.OperatorEnum.EQ,
               '!=': _CommonService.OperatorEnum.NE,
               '>':  _CommonService.OperatorEnum.GT,
               '>=': _CommonService.OperatorEnum.GTE,
               '<':  _CommonService.OperatorEnum.LT,
               '<=': _CommonService.OperatorEnum.LTE}
    _OP_PATTERN = re.compile(r"({})".format('|'.join(sorted(six.viewkeys(_OP_MAP), key=lambda s: len(s), reverse=True))))

    # keys that yield predictable, sensible results
    _VALID_QUERY_KEYS = {
        'id', 'project_id', 'experiment_id',
        'date_created', 'date_updated', 'start_time', 'end_time',
        'tags', 'attributes', 'hyperparameters', 'metrics',
    }

    def __init__(self, conn, conf, expt_run_ids=None):
        self._conn = conn
        self._conf = conf
        self._ids = expt_run_ids if expt_run_ids is not None else []

    def __repr__(self):
        return "<ExperimentRuns containing {} runs>".format(self.__len__())

    def __getitem__(self, key):
        if isinstance(key, int):
            expt_run_id = self._ids[key]
            return ExperimentRun(self._conn, self._conf, _expt_run_id=expt_run_id)
        elif isinstance(key, slice):
            expt_run_ids = self._ids[key]
            return self.__class__(self._conn, self._conf, expt_run_ids)
        else:
            raise TypeError("index must be integer or slice, not {}".format(type(key)))

    def __len__(self):
        return len(self._ids)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            self_ids_set = set(self._ids)
            other_ids = [expt_run_id for expt_run_id in other._ids if expt_run_id not in self_ids_set]
            return self.__class__(self._conn, self._conf, self._ids + other_ids)
        else:
            return NotImplemented

    def find(self, where, ret_all_info=False, _proj_id=None, _expt_id=None):
        """
        Gets the Experiment Runs from this collection that match predicates `where`.

        .. deprecated:: 0.13.3
           The `ret_all_info` parameter will removed in v0.14.0.

        A predicate in `where` is a string containing a simple boolean expression consisting of:

            - a dot-delimited Experiment Run property such as ``metrics.accuracy``
            - a Python boolean operator such as ``>=``
            - a literal value such as ``.8``

        Parameters
        ----------
        where : str or list of str
            Predicates specifying Experiment Runs to get.

        Returns
        -------
        :class:`ExperimentRuns`

        Warnings
        --------
        This feature is still in active development. It is completely safe to use, but may exhibit
        unintuitive behavior. Please report any oddities to the Verta team!

        Examples
        --------
        >>> runs.find(["hyperparameters.hidden_size == 256",
        ...            "metrics.accuracy >= .8"])
        <ExperimentRuns containing 3 runs>

        """
        if ret_all_info:
            warnings.warn("`ret_all_info` is deprecated and will removed in a later version",
                          category=FutureWarning)

        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._conn, self._conf)
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
                six.raise_from(ValueError("predicate `{}` must be a two-operand comparison".format(predicate)),
                               None)

            if key.split('.')[0] not in self._VALID_QUERY_KEYS:
                raise ValueError("key `{}` is not a valid key for querying;"
                                 " currently supported keys are: {}".format(key, self._VALID_QUERY_KEYS))

            # cast operator into protobuf enum variant
            operator = self._OP_MAP[operator]

            # parse value
            try:
                expr_node = ast.parse(value, mode='eval')
            except SyntaxError:
                six.raise_from(ValueError("value `{}` must be a number or string literal".format(value)),
                               None)
            value_node = expr_node.body
            if type(value_node) is ast.Num:
                value = value_node.n
            elif type(value_node) is ast.Str:
                value = value_node.s
            elif type(value_node) is ast.Compare:
                raise ValueError("predicate `{}` must be a two-operand comparison".format(predicate))
            else:
                raise ValueError("value `{}` must be a number or string literal".format(value))

            predicates.append(_CommonService.KeyValueQuery(key=key, value=_utils.python_to_val_proto(value),
                                                           operator=operator))
        Message = _ExperimentRunService.FindExperimentRuns
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      predicates=predicates, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/findExperimentRuns".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._conn, self._conf, [expt_run.id for expt_run in response_msg.experiment_runs])

    def sort(self, key, descending=False, ret_all_info=False):
        """
        Sorts the Experiment Runs from this collection by `key`.

        .. deprecated:: 0.13.3
           The `ret_all_info` parameter will removed in v0.14.0.

        A `key` is a string containing a dot-delimited Experiment Run property such as
        ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        descending : bool, default False
            Order in which to return sorted Experiment Runs.

        Returns
        -------
        :class:`ExperimentRuns`

        Warnings
        --------
        This feature is still in active development. It is completely safe to use, but may exhibit
        unintuitive behavior. Please report any oddities to the Verta team!

        Examples
        --------
        >>> runs.sort("metrics.accuracy")
        <ExperimentRuns containing 3 runs>

        """
        if ret_all_info:
            warnings.warn("`ret_all_info` is deprecated and will removed in a later version",
                          category=FutureWarning)

        if key.split('.')[0] not in self._VALID_QUERY_KEYS:
            raise ValueError("key `{}` is not a valid key for querying;"
                             " currently supported keys are: {}".format(key, self._VALID_QUERY_KEYS))
        if self.__len__() == 0:
            return self.__class__(self._conn, self._conf)

        Message = _ExperimentRunService.SortExperimentRuns
        msg = Message(experiment_run_ids=self._ids,
                      sort_key=key, ascending=not descending, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/sortExperimentRuns".format(self._conn.scheme, self._conn.socket),
                                       self._conn,
                                       params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._conn, self._conf, [expt_run.id for expt_run in response_msg.experiment_runs])

    def top_k(self, key, k, ret_all_info=False, _proj_id=None, _expt_id=None):
        r"""
        Gets the Experiment Runs from this collection with the `k` highest `key`\ s.

        .. deprecated:: 0.13.3
           The `ret_all_info` parameter will removed in v0.14.0.

        A `key` is a string containing a dot-delimited Experiment Run property such as
        ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.

        Returns
        -------
        :class:`ExperimentRuns`

        Warnings
        --------
        This feature is still in active development. It is completely safe to use, but may exhibit
        unintuitive behavior. Please report any oddities to the Verta team!

        Examples
        --------
        >>> runs.top_k("metrics.accuracy", 3)
        <ExperimentRuns containing 3 runs>

        """
        if ret_all_info:
            warnings.warn("`ret_all_info` is deprecated and will removed in a later version",
                          category=FutureWarning)

        if key.split('.')[0] not in self._VALID_QUERY_KEYS:
            raise ValueError("key `{}` is not a valid key for querying;"
                             " currently supported keys are: {}".format(key, self._VALID_QUERY_KEYS))
        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._conn, self._conf)
            else:
                expt_run_ids = self._ids
        else:
            expt_run_ids = None

        Message = _ExperimentRunService.TopExperimentRunsSelector
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      sort_key=key, ascending=False, top_k=k, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getTopExperimentRuns".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._conn, self._conf, [expt_run.id for expt_run in response_msg.experiment_runs])

    def bottom_k(self, key, k, ret_all_info=False, _proj_id=None, _expt_id=None):
        r"""
        Gets the Experiment Runs from this collection with the `k` lowest `key`\ s.

        .. deprecated:: 0.13.3
           The `ret_all_info` parameter will removed in v0.14.0.

        A `key` is a string containing a dot-delimited Experiment Run property such as ``metrics.accuracy``.

        Parameters
        ----------
        key : str
            Dot-delimited Experiment Run property.
        k : int
            Number of Experiment Runs to get.

        Returns
        -------
        :class:`ExperimentRuns`

        Warnings
        --------
        This feature is still in active development. It is completely safe to use, but may exhibit
        unintuitive behavior. Please report any oddities to the Verta team!

        Examples
        --------
        >>> runs.bottom_k("metrics.loss", 3)
        <ExperimentRuns containing 3 runs>

        """
        if ret_all_info:
            warnings.warn("`ret_all_info` is deprecated and will removed in a later version",
                          category=FutureWarning)

        if key.split('.')[0] not in self._VALID_QUERY_KEYS:
            raise ValueError("key `{}` is not a valid key for querying;"
                             " currently supported keys are: {}".format(key, self._VALID_QUERY_KEYS))
        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._conn, self._conf)
            else:
                expt_run_ids = self._ids
        else:
            expt_run_ids = None

        Message = _ExperimentRunService.TopExperimentRunsSelector
        msg = Message(project_id=_proj_id, experiment_id=_expt_id, experiment_run_ids=expt_run_ids,
                      sort_key=key, ascending=True, top_k=k, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getTopExperimentRuns".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._conn, self._conf, [expt_run.id for expt_run in response_msg.experiment_runs])


class ExperimentRun(_ModelDBEntity):
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
    def __init__(self, conn, conf,
                 proj_id=None, expt_id=None, expt_run_name=None,
                 desc=None, tags=None, attrs=None,
                 _expt_run_id=None):
        if expt_run_name is not None and _expt_run_id is not None:
            raise ValueError("cannot specify both `expt_run_name` and `_expt_run_id`")

        if _expt_run_id is not None:
            expt_run = ExperimentRun._get(conn, _expt_run_id=_expt_run_id)
            if expt_run is not None:
                pass
            else:
                raise ValueError("ExperimentRun with ID {} not found".format(_expt_run_id))
        elif None not in (proj_id, expt_id):
            if expt_run_name is None:
                expt_run_name = ExperimentRun._generate_default_name()
            try:
                expt_run = ExperimentRun._create(conn, proj_id, expt_id, expt_run_name, desc, tags, attrs)
            except requests.HTTPError as e:
                if e.response.status_code == 409:  # already exists
                    if any(param is not None for param in (desc, tags, attrs)):
                        warnings.warn("ExperimentRun with name {} already exists;"
                                      " cannot initialize `desc`, `tags`, or `attrs`".format(expt_run_name))
                    expt_run = ExperimentRun._get(conn, expt_id, expt_run_name)
                    print("set existing ExperimentRun: {}".format(expt_run.name))
                else:
                    raise e
            else:
                print("created new ExperimentRun: {}".format(expt_run.name))
        else:
            raise ValueError("insufficient arguments")

        super(ExperimentRun, self).__init__(conn, conf, _ExperimentRunService, "experiment-run", expt_run.id)

    def __repr__(self):
        Message = _ExperimentRunService.GetExperimentRunById
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getExperimentRunById".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        run_msg = response_msg.experiment_run
        return '\n'.join((
            "name: {}".format(run_msg.name),
            "url: {}://{}/project/{}/exp-runs/{}".format(self._conn.scheme, self._conn.socket, run_msg.project_id, self.id),
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
                                       "{}://{}/v1/experiment-run/getExperimentRunById".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.experiment_run.name

    @staticmethod
    def _generate_default_name():
        return "Run {}".format(_utils.generate_default_name())

    @staticmethod
    def _get(conn, expt_id=None, expt_run_name=None, _expt_run_id=None):
        if _expt_run_id is not None:
            Message = _ExperimentRunService.GetExperimentRunById
            msg = Message(id=_expt_run_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment-run/getExperimentRunById".format(conn.scheme, conn.socket),
                                           conn, params=data)
        elif None not in (expt_id, expt_run_name):
            Message = _ExperimentRunService.GetExperimentRunByName
            msg = Message(experiment_id=expt_id, name=expt_run_name)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment-run/getExperimentRunByName".format(conn.scheme, conn.socket),
                                           conn, params=data)
        else:
            raise ValueError("insufficient arguments")

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment_run
        else:
            if response.status_code == 404 and response.json()['code'] == 5:
                return None
            else:
                _utils.raise_for_http_error(response)

    @staticmethod
    def _create(conn, proj_id, expt_id, expt_run_name, desc=None, tags=None, attrs=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        Message = _ExperimentRunService.CreateExperimentRun
        msg = Message(project_id=proj_id, experiment_id=expt_id, name=expt_run_name,
                      description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/createExperimentRun".format(conn.scheme, conn.socket),
                                       conn, json=data)

        if response.ok:
            response_msg = _utils.json_to_proto(response.json(), Message.Response)
            return response_msg.experiment_run
        else:
            _utils.raise_for_http_error(response)

    def _log_artifact(self, key, artifact, artifact_type, extension=None):
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
        extension : str, optional
            Filename extension associated with the artifact.

        """
        if isinstance(artifact, six.string_types):
            artifact = open(artifact, 'rb')

        artifact_stream, method = _artifact_utils.ensure_bytestream(artifact)

        if extension is None:
            extension = _artifact_utils.ext_from_method(method)

        # calculate checksum
        artifact_hash = hashlib.sha256(artifact_stream.read()).hexdigest()
        artifact_stream.seek(0)

        # determine basename
        #     The key might already contain the file extension, thanks to our hard-coded deployment
        #     keys e.g. "model.pkl" and "model_api.json".
        if key.endswith(os.extsep + extension):
            basename = key
        else:
            basename = key + os.extsep + extension

        # build upload path from checksum and basename
        artifact_path = os.path.join(artifact_hash, basename)

        # log key to ModelDB
        Message = _ExperimentRunService.LogArtifact
        artifact_msg = _CommonService.Artifact(key=key,
                                               path=artifact_path,
                                               path_only=False,
                                               artifact_type=artifact_type,
                                               filename_extension=extension)
        msg = Message(id=self.id, artifact=artifact_msg)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logArtifact".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("artifact with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                _utils.raise_for_http_error(response)

        # upload artifact to artifact store
        url = self._get_url_for_artifact(key, "PUT")
        artifact_stream.seek(0)  # reuse stream that was created for checksum
        if self._conf.debug:
            print("[DEBUG] uploading {} bytes ({})".format(len(artifact_stream.read()), basename))
            artifact_stream.seek(0)
        response = _utils.make_request("PUT", url, self._conn, data=artifact_stream)
        _utils.raise_for_http_error(response)
        print("upload complete ({})".format(basename))

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
                                       "{}://{}/v1/experiment-run/logArtifact".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("artifact with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                _utils.raise_for_http_error(response)

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
        Message = _CommonService.GetArtifacts
        msg = Message(id=self.id, key=key)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getArtifacts".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        artifact = {artifact.key: artifact for artifact in response_msg.artifacts}.get(key)
        if artifact is None:
            raise KeyError("no artifact found with key {}".format(key))
        if artifact.path_only:
            return artifact.path, artifact.path_only
        else:
            # download artifact from artifact store
            url = self._get_url_for_artifact(key, "GET")
            response = _utils.make_request("GET", url, self._conn)
            _utils.raise_for_http_error(response)

            return response.content, artifact.path_only

    # TODO: Fix up get dataset to handle the Dataset class when logging dataset
    # version
    def _get_dataset(self, key):
        """
        Gets the dataset with name `key` from this Experiment Run.

        If the dataset was originally logged as just a filesystem path, that path will be returned.
        Otherwise, bytes representing the dataset object will be returned.

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
        Message = _ExperimentRunService.GetDatasets
        msg = Message(id=self.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/getDatasets".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        dataset = {dataset.key: dataset for dataset in response_msg.datasets}.get(key)
        if dataset is None:
            # may be old artifact-based dataset
            try:
                dataset, path_only = self._get_artifact(key)
            except KeyError:
                six.raise_from(KeyError("no dataset found with key {}".format(key)),
                               None)
            else:
                return dataset, path_only, None
        else:
            return dataset.path, dataset.path_only, dataset.linked_artifact_id

    def log_tag(self, tag):
        """
        Logs a tag to this Experiment Run.

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
                                       "{}://{}/v1/experiment-run/addExperimentRunTags".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/addExperimentRunTags".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/getExperimentRunTags".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.tags

    def log_attribute(self, key, value):
        """
        Logs an attribute to this Experiment Run.

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
                                       "{}://{}/v1/experiment-run/logAttribute".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("attribute with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/logAttributes".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("some attribute with some input key already exists;"
                                 " consider using observations instead")
            else:
                _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/getAttributes".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        attributes = _utils.unravel_key_values(response_msg.attributes)
        try:
            return attributes[key]
        except KeyError:
            six.raise_from(KeyError("no attribute found with key {}".format(key)), None)

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
                                       "{}://{}/v1/experiment-run/getAttributes".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_key_values(response_msg.attributes)

    def log_metric(self, key, value):
        """
        Logs a metric to this Experiment Run.

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
                                       "{}://{}/v1/experiment-run/logMetric".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("metric with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/logMetrics".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("some metric with some input key already exists;"
                                 " consider using observations instead")
            else:
                _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/getMetrics".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        metrics = _utils.unravel_key_values(response_msg.metrics)
        try:
            return metrics[key]
        except KeyError:
            six.raise_from(KeyError("no metric found with key {}".format(key)), None)

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
                                       "{}://{}/v1/experiment-run/getMetrics".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_key_values(response_msg.metrics)

    def log_hyperparameter(self, key, value):
        """
        Logs a hyperparameter to this Experiment Run.

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
                                       "{}://{}/v1/experiment-run/logHyperparameter".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("hyperparameter with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/logHyperparameters".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("some hyperparameter with some input key already exists;"
                                 " consider using observations instead")
            else:
                _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/getHyperparameters".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        hyperparameters = _utils.unravel_key_values(response_msg.hyperparameters)
        try:
            return hyperparameters[key]
        except KeyError:
            six.raise_from(KeyError("no hyperparameter found with key {}".format(key)), None)

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
                                       "{}://{}/v1/experiment-run/getHyperparameters".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

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
                - If type is Dataset, then it will log a dataset version
                - Otherwise, the object will be serialized and uploaded as an artifact.

        """
        _utils.validate_flat_key(key)

        if isinstance(dataset, _dataset.Dataset):
            raise ValueError("directly logging a Dataset is not supported;"
                             " consider using run.log_dataset_version() instead")

        if isinstance(dataset, _dataset.DatasetVersion):
            # TODO: maybe raise a warning pointing to log_dataset_version()
            self.log_dataset_version(key, dataset)

        # log `dataset` as artifact
        try:
            extension = _artifact_utils.get_file_ext(dataset)
        except (TypeError, ValueError):
            extension = None
        self._log_artifact(key, dataset, _CommonService.ArtifactTypeEnum.DATA, extension)

    def log_dataset_version(self, key, dataset_version):
        """
        Logs a Verta DatasetVersion to this ExperimentRun with the given key.

        Parameters
        ----------
        key : str
        dataset_version : :class:`~verta._dataset.DatasetVersion`

        """
        if not isinstance(dataset_version, _dataset.DatasetVersion):
            raise ValueError("`dataset_version` must be of type DatasetVersion")

        # TODO: hack because path_only artifact needs a placeholder path
        dataset_path = "See attached dataset version"

        # log key-path to ModelDB
        Message = _ExperimentRunService.LogDataset
        artifact_msg = _CommonService.Artifact(key=key,
                                               path=dataset_path,
                                               path_only=True,
                                               artifact_type=_CommonService.ArtifactTypeEnum.DATA,
                                               linked_artifact_id=dataset_version.id)
        msg = Message(id=self.id, dataset=artifact_msg)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/experiment-run/logDataset".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        if not response.ok:
            if response.status_code == 409:
                raise ValueError("dataset with key {} already exists;"
                                 " consider using observations instead".format(key))
            else:
                _utils.raise_for_http_error(response)

    def log_dataset_path(self, key, path):
        """
        Logs the filesystem path of an dataset to this Experiment Run.

        .. deprecated:: 0.13.0
           The `log_dataset_path()` method will removed in v0.14.0; consider using
           `client.set_dataset(…, type="local")` and `run.log_dataset_version()` instead.

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

        warnings.warn("`log_dataset_path()` is deprecated and will removed in a later version;"
                      " consider using `client.set_dataset(..., type=\"local\")`"
                      " and `run.log_dataset_version()` instead",
                      category=FutureWarning)

        # create impromptu DatasetVersion
        dataset = _dataset.LocalDataset(self._conn, self._conf, name=key)
        dataset_version = dataset.create_version(path=path)

        self.log_dataset_version(key, dataset_version)

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
            DatasetVersion if logged using :meth:`log_dataset_version()`.
            Filesystem path of the dataset, the dataset object, or a bytestream representing the
            dataset.

        """
        dataset, path_only, linked_id = self._get_dataset(key)
        if path_only:
            if linked_id:
                return _dataset.DatasetVersion(self._conn, self._conf, _dataset_version_id=linked_id)
            else:
                return dataset
        else:
            # TODO: may need to be updated for raw
            try:
                return pickle.loads(dataset)
            except pickle.UnpicklingError:
                return six.BytesIO(dataset)

    def get_dataset_version(self, key):
        """
        Gets the DatasetVersion with name `key` from this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the dataset version.

        Returns
        -------
        DatasetVersion
            DatasetVersion associated with the given key.

        """
        return self.get_dataset(key)

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
        if self._conf.debug:
            if not hasattr(model, 'read'):
                print("[DEBUG] model is type: {}".format(model.__class__))
        _artifact_utils.reset_stream(model)  # reset cursor to beginning in case user forgot
        try:
            model_extension = _artifact_utils.get_file_ext(model)
        except (TypeError, ValueError):
            model_extension = None
        model, method, model_type = _artifact_utils.serialize_model(model)
        if method is None:
            raise ValueError("will not be able to deploy model due to unknown serialization method")
        if model_extension is None:
            model_extension = _artifact_utils.ext_from_method(method)

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
        if self._conf.debug:
            print("[DEBUG] model API is:")
            pprint.pprint(model_api.to_dict())

        # prehandle requirements
        _artifact_utils.reset_stream(requirements)  # reset cursor to beginning in case user forgot
        _artifact_utils.validate_requirements_txt(requirements)
        req_deps = six.ensure_str(requirements.read()).splitlines()  # get list repr of reqs
        _artifact_utils.reset_stream(requirements)  # reset cursor to beginning as a courtesy
        # add verta to requirements
        verta_dep = "verta=={}".format(__about__.__version__)
        for req_dep in req_deps:
            if req_dep.startswith("verta"):  # if present, check version
                our_ver = verta_dep.split('==')[-1]
                their_ver = req_dep.split('==')[-1]
                if our_ver != their_ver:  # versions conflict, so raise exception
                    raise ValueError("Client is running with verta v{}, but the provided requirements specify v{}; "
                                     "these must match".format(our_ver, their_ver))
                else:  # versions match, so proceed
                    break
        else:  # if not present, add
            req_deps.append(verta_dep)
        # if cloudpickle used, add to requirements
        if method == "cloudpickle":
            cloudpickle_dep = "cloudpickle=={}".format(_artifact_utils.cloudpickle.__version__)
            for req_dep in req_deps:
                if req_dep.startswith("cloudpickle"):  # if present, check version
                    our_ver = cloudpickle_dep.split('==')[-1]
                    their_ver = req_dep.split('==')[-1]
                    if our_ver != their_ver:  # versions conflict, so raise exception
                        raise ValueError("Client is running with cloudpickle v{}, but the provided requirements specify v{}; "
                                         "these must match".format(our_ver, their_ver))
                    else:  # versions match, so proceed
                        break
            else:  # if not present, add
                req_deps.append(cloudpickle_dep)
        # recreate stream
        requirements = six.BytesIO(six.ensure_binary('\n'.join(req_deps)))
        if self._conf.debug:
            print("[DEBUG] requirements are:")
            print(six.ensure_str(requirements.read()))
            requirements.seek(0)

        # prehandle train_features and train_targets
        if train_features is not None and train_targets is not None:
            stringstream = six.StringIO()
            train_df = train_features.join(train_targets)
            train_df.to_csv(stringstream, index=False)  # write as CSV
            stringstream.seek(0)
            train_data = stringstream
        else:
            train_data = None

        self._log_artifact("model.pkl", model, _CommonService.ArtifactTypeEnum.MODEL, model_extension)
        self._log_artifact("model_api.json", model_api, _CommonService.ArtifactTypeEnum.BLOB, 'json')
        self._log_artifact("requirements.txt", requirements, _CommonService.ArtifactTypeEnum.BLOB, 'txt')
        if train_data is not None:
            self._log_artifact("train_data", train_data, _CommonService.ArtifactTypeEnum.DATA, 'csv')

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

        try:
            extension = _artifact_utils.get_file_ext(model)
        except (TypeError, ValueError):
            extension = None

        model, method, _ = _artifact_utils.serialize_model(model)

        if extension is None:
            extension = _artifact_utils.ext_from_method(method)

        self._log_artifact(key, model, _CommonService.ArtifactTypeEnum.MODEL, extension)

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
        bytestream, extension = six.BytesIO(), 'png'
        try:  # handle matplotlib
            image.savefig(bytestream, format=extension)
        except AttributeError:
            try:  # handle PIL Image
                colors = image.getcolors()
            except AttributeError:
                try:
                    extension = _artifact_utils.get_file_ext(image)
                except (TypeError, ValueError):
                    extension = None
            else:
                if len(colors) == 1 and all(val == 255 for val in colors[0][1]):
                    warnings.warn("the image being logged is blank")
                image.save(bytestream, extension)

        bytestream.seek(0)
        if bytestream.read(1):
            bytestream.seek(0)
            image = bytestream

        self._log_artifact(key, image, _CommonService.ArtifactTypeEnum.IMAGE, extension)

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
        image, path_only = self._get_artifact(key)
        if path_only:
            return image
        else:
            if PIL is None:  # Pillow not installed
                return six.BytesIO(image)
            try:
                return PIL.Image.open(six.BytesIO(image))
            except IOError:  # can't be handled by Pillow
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

        try:
            extension = _artifact_utils.get_file_ext(artifact)
        except (TypeError, ValueError):
            extension = None

        self._log_artifact(key, artifact, _CommonService.ArtifactTypeEnum.BLOB, extension)

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
        artifact, path_only = self._get_artifact(key)
        if path_only:
            return artifact
        else:
            try:
                return pickle.loads(artifact)
            except:
                return six.BytesIO(artifact)

    def log_observation(self, key, value, timestamp=None):
        """
        Logs an observation to this Experiment Run.

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
                                       "{}://{}/v1/experiment-run/logObservation".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
        _utils.raise_for_http_error(response)

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
                                       "{}://{}/v1/experiment-run/getObservations".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if len(response_msg.observations) == 0:
            raise KeyError("no observation found with key {}".format(key))
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
                                       "{}://{}/v1/experiment-run/getExperimentRunById".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        _utils.raise_for_http_error(response)

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_observations(response_msg.experiment_run.observations)

    def log_modules(self, paths, search_path=None):
        """
        Logs local files that are dependencies for a deployed model to this Experiment Run.

        .. deprecated:: 0.12.4
           The `search_path` parameter is no longer necessary and will removed in v0.14.0; consider
           removing it from the function call.

        Parameters
        ----------
        paths : str or list of str
            Paths to local Python modules and other files that the deployed model depends on. If a
            directory is provided, all files within will be included.

        """
        if search_path is not None:
            warnings.warn("`search_path` is no longer used and will removed in a later version;"
                          " consider removing it from the function call",
                          category=FutureWarning)
        if isinstance(paths, six.string_types):
            paths = [paths]

        CUSTOM_MODULES_DIR = "/app/custom_modules/"  # location in DeploymentService model container

        # convert into absolute paths
        paths = map(os.path.abspath, paths)
        # add trailing separator to directories
        paths = [os.path.join(path, "") if os.path.isdir(path) else path
                 for path in paths]

        # obtain deepest common directory
        curr_dir = os.path.join(os.getcwd(), "")
        paths_plus = paths + [curr_dir]
        common_prefix = os.path.commonprefix(paths_plus)
        common_dir = os.path.dirname(common_prefix)

        filepaths = _utils.find_filepaths(paths, include_hidden=True, include_venv=False)

        # get search paths to modify Deployment's sys.path
        if self._conf.debug:
            print("[DEBUG] sys.path is:")
            pprint.pprint(sys.path)
        # convert into absolute paths
        search_paths = list(map(os.path.abspath, sys.path))
        # only consider search paths inside common directory
        search_paths = list(filter(lambda path: path.startswith(common_dir), search_paths))
        # strip common directory
        search_paths = list(map(lambda path: os.path.relpath(path, common_dir), search_paths))
        # append to Deployment's custom modules directory
        search_paths = list(map(lambda path: os.path.join(CUSTOM_MODULES_DIR, path), search_paths))
        if self._conf.debug:
            print("[DEBUG] deployment search paths are:")
            pprint.pprint(search_paths)

        bytestream = six.BytesIO()
        with zipfile.ZipFile(bytestream, 'w') as zipf:
            for filepath in filepaths:
                zipf.write(filepath, os.path.relpath(filepath, common_dir))
            working_dir = os.path.join(CUSTOM_MODULES_DIR, os.path.relpath(curr_dir, common_dir))
            zipf.writestr(
                "_verta_config.py",
                six.ensure_binary('\n'.join([
                    "import os, sys",
                    "",
                    "",
                    "sys.path = sys.path[:1] + {} + sys.path[1:]".format(list(search_paths)),
                    "",
                    "try:",
                    "    os.makedirs(\"{}\")".format(working_dir),
                    "except OSError:  # already exists",
                    "    pass",
                    "os.chdir(\"{}\")".format(working_dir),
                ]))
            )
            if self._conf.debug:
                print("[DEBUG] archive contains:")
                zipf.printdir()
        bytestream.seek(0)

        self._log_artifact("custom_modules", bytestream, _CommonService.ArtifactTypeEnum.BLOB, 'zip')

    def log_setup_script(self, script):
        """
        Associate a model deployment setup script with this Experiment Run.

        .. versionadded:: 0.13.8

        Parameters
        ----------
        script : str
            String composed of valid Python code for executing setup steps at the beginning of model
            deployment. An on-disk file can be passed in using ``open("path/to/file.py", 'r').read()``.

        Raises
        ------
        SyntaxError
            If `script` contains invalid Python.

        """
        # validate `script`'s syntax
        try:
            ast.parse(script)
        except SyntaxError as e:
            # clarify that the syntax error comes from `script`, and propagate details
            reason = e.args[0]
            line_no = e.args[1][1]
            line = script.splitlines()[line_no-1]
            six.raise_from(SyntaxError("{} in provided script on line {}:\n{}"
                                       .format(reason, line_no, line)),
                           e)

        # convert into bytes for upload
        script = six.ensure_binary(script)

        # convert to file-like for `_log_artifact()`
        script = six.BytesIO(script)

        self._log_artifact("setup_script", script, _CommonService.ArtifactTypeEnum.BLOB, 'py')
