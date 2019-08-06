import six
import six.moves.cPickle as pickle
from six.moves.urllib.parse import urlparse

import ast
import hashlib
import os
import pprint
import re
import sys
import time
import warnings
import zipfile

import PIL
import requests

try:
    from google.cloud import bigquery
except ImportError:  # BigQuery not installed
    pass
else:
    import datetime  # TODO: remove this
    import pytz

try:
    from boto3 import client as BotoClient
except ImportError:  # Boto 3 not installed
    pass
else:
    import datetime  # TODO: remove this
    import pytz  # TODO: remove this
    import dateutil

from ._protos.public.modeldb import CommonService_pb2 as _CommonService
from ._protos.public.modeldb import ProjectService_pb2 as _ProjectService
from ._protos.public.modeldb import ExperimentService_pb2 as _ExperimentService
from ._protos.public.modeldb import ExperimentRunService_pb2 as _ExperimentRunService
from ._protos.public.modeldb import DatasetService_pb2 as _DatasetService
from ._protos.public.modeldb import DatasetVersionService_pb2 as _DatasetVersionService
from . import _utils
from . import _artifact_utils
from . import utils


class Client:
    """
    Object for interfacing with the ModelDB backend.

    This class provides functionality for starting/resuming Projects, Experiments, and Experiment Runs.

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
    use_git : bool
        Whether to use a local Git repository for certain operations. Changes to this value propagate
        to any objects that are/were created from this Client.
    proj : :class:`Project` or None
        Currently active Project.
    expt : :class:`Experiment` or None
        Currently active Experiment.
    expt_runs : :class:`ExperimentRuns` or None
        ExperimentRuns under the currently active Experiment.

    """
    _GRPC_PREFIX = "Grpc-Metadata-"

    def __init__(self, host, port=None, email=None, dev_key=None,
                 max_retries=5, ignore_conn_err=False, use_git=True, debug=False):
        if email is None and 'VERTA_EMAIL' in os.environ:
            email = os.environ['VERTA_EMAIL']
            print("set email from environment")
        if dev_key is None and 'VERTA_DEV_KEY' in os.environ:
            dev_key = os.environ.get('VERTA_DEV_KEY')
            print("set developer key from environment")

        if email is None and dev_key is None:
            if debug:
                print("[DEBUG] email and developer key not found; auth disabled")
            auth = None
            scheme = "http"
        elif email is not None and dev_key is not None:
            if debug:
                print("[DEBUG] using email: {}".format(email))
                print("[DEBUG] using developer key: {}".format(dev_key[:8] + re.sub(r"[^-]", '*', dev_key[8:])))
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

        # verify connection
        socket = host if port is None else "{}:{}".format(host, port)
        conn = _utils.Connection(scheme, socket, auth, max_retries, ignore_conn_err)
        try:
            response = _utils.make_request("GET",
                                           "{}://{}/v1/project/verifyConnection".format(conn.scheme, conn.socket),
                                           conn)
        except requests.ConnectionError:
            six.raise_from(requests.ConnectionError("connection failed; please check `host` and `port`"),
                           None)
        response.raise_for_status()
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
    def debug(self):
        return self._conf.debug

    @debug.setter
    def debug(self, value):
        self._conf.debug = value

    @property
    def expt_runs(self):
        if self.expt is None:
            return None
        else:
            Message = _ExperimentRunService.GetExperimentRunsInProject
            msg = Message(project_id=self.proj.id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/experiment-run/getExperimentRunsInProject".format(self._conn.scheme, self._conn.socket),
                                           self._conn, params=data)
            response.raise_for_status()

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

        proj = Project(self._conn, self._conf,
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

        expt = Experiment(self._conn, self._conf,
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

        return ExperimentRun(self._conn, self._conf,
                             self.proj.id, self.expt.id, name,
                             desc, tags, attrs)

    # NOTE: dataset visibility cannot be set via a client
    def create_dataset(self, name=None, dataset_type=None, desc=None, tags=None,
    attrs=None, id=None):
        return Dataset(self._conn, self._conf, name=name, dataset_type=dataset_type,
            desc=desc, tags=tags, attrs=attrs, _dataset_id=id)

    # TODO: needs a by name after backend implements
    def get_dataset(self, id):
        return Dataset._get(self._conn, _dataset_id=id)

    # TODO: needs to be paginated, maybe sorted and filtered
    def get_all_datasets(self):
        Message = _DatasetService.GetAllDatasets
        msg = Message()
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                        "{}://{}/v1/dataset/getAllDatasets".format(self._conn.scheme, self._conn.socket),
                                        self._conn, params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return [Dataset(self._conn, self._conf, _dataset_id = dataset.id)
                for dataset in response_msg.datasets]

    def create_dataset_version(self, dataset, dataset_version_info,
        parent_id=None, desc=None, tags=None, dataset_type=None, attrs=None,
        version=None, id=None):
        return DatasetVersion(self._conn, self._conf, dataset_id=dataset.id,
            dataset_type=dataset.dataset_type,
            dataset_version_info=dataset_version_info, parent_id=parent_id,
            desc=desc, tags=tags, attrs=attrs, version=version, _dataset_version_id=id)

    # TODO: this should also allow gets based on dataset_id and version, but
    # not supported by backend yet
    def get_dataset_version(self, id):
        return DatasetVersion._get(self._conn, _dataset_version_id=id)

    def get_all_versions_for_dataset(self, dataset):
        Message = _DatasetVersionService.GetAllDatasetVersionsByDatasetId
        msg = Message(dataset_id=dataset.id)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                        "{}://{}/v1/dataset-version/getAllDatasetVersionsByDatasetId".format(self._conn.scheme, self._conn.socket),
                                        self._conn, params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return [DatasetVersion(self._conn, self._conf, _dataset_version_id = dataset_version.id)
                for dataset_version in response_msg.dataset_versions]

    # TODO: sorting seems to be incorrect
    def get_latest_version_for_dataset(self, dataset, ascending=None, sort_key=None):
        Message = _DatasetVersionService.GetLatestDatasetVersionByDatasetId
        msg = Message(dataset_id=dataset.id, ascending=ascending, sort_key=sort_key)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                        "{}://{}/v1/dataset-version/getLatestDatasetVersionByDatasetId".format(self._conn.scheme, self._conn.socket),
                                        self._conn, params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return response_msg.dataset_version

    def create_s3_dataset(self, name):
        return self.create_dataset(name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)

    def create_s3_dataset_version(self, dataset, bucket_name, key=None,
        url_stub=None, parent_id=None, desc=None, tags=None, attrs=None):
        s3_dataset_version_info = S3DatasetVersionInfo(bucket_name, key=key,
            url_stub=url_stub)
        return PathDatasetVersion(self._conn, self._conf, dataset_id=dataset.id,
            dataset_type=dataset.dataset_type,
            dataset_version_info=s3_dataset_version_info, parent_id=parent_id,
            desc=desc, tags=tags, attrs=attrs)

    def create_local_dataset(self, name):
        return self.create_dataset(name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)

    def create_local_dataset_version(self, dataset, path,
        parent_id=None, desc=None, tags=None, attrs=None):
        filesystem_dataset_version_info = FilesystemDatasetVersionInfo(path)
        return PathDatasetVersion(self._conn, self._conf, dataset_id=dataset.id,
            dataset_type=dataset.dataset_type,
            dataset_version_info=filesystem_dataset_version_info, parent_id=parent_id,
            desc=desc, tags=tags, attrs=attrs)

    def create_big_query_dataset(self, name):
        return self.create_dataset(name, dataset_type=_DatasetService.DatasetTypeEnum.QUERY)

    def create_big_query_dataset_version(self, dataset, job_id, location,
        parent_id=None, desc=None, tags=None, attrs=None):
        filesystem_dataset_version_info = BigQueryDatasetVersionInfo(
            job_id=job_id, location=location)
        return QueryDatasetVersion(self._conn, self._conf, dataset_id=dataset.id,
            dataset_type=dataset.dataset_type,
            dataset_version_info=filesystem_dataset_version_info, parent_id=parent_id,
            desc=desc, tags=tags, attrs=attrs)


class Dataset:
    # TODO: delete is not supported on the API yet
    def __init__(self, conn, conf,
        name=None, dataset_type=None, desc=None, tags=None, attrs=None, _dataset_id=None):
        if name is not None and _dataset_id is not None:
            raise ValueError("cannot specify both `name` and `_dataset_id`")

        # retrieve dataset by id
        if _dataset_id is not None:
            dataset = Dataset._get(conn, _dataset_id=_dataset_id)
            if dataset is None:
                raise ValueError("Dataset with ID {} not found".format(_dataset_id))
        else:
            # create a new dataset
            if name is None:
                name = Dataset._generate_default_name()
            try:
                dataset = Dataset._create(conn, name, dataset_type, desc, tags, attrs)
            except requests.HTTPError as e:
                if e.response.status_code == 409:  # already exists
                    if any(param is not None for param in (desc, tags, attrs)):
                        warnings.warn("Dataset with name {} already exists;"
                                        " cannot initialize `desc`, `tags`, or `attrs`".format(name))
                    dataset = Dataset._get(conn, name)
                else:
                    raise e
            else:
                print("created new Dataset: {}".format(dataset.name))

        # this is available to create versions
        self._conn = conn
        self._conf = conf

        self.id = dataset.id

        # these could be updated by separate calls
        self.name = dataset.name
        self.dataset_type = dataset.dataset_type
        self.desc = dataset.description
        self.attrs = dataset.attributes
        self.tags = dataset.tags

    def __repr__(self):
        return "<Dataset \"{}\">".format(self.name)

    @staticmethod
    def _generate_default_name():
        return "Dataset {}".format(_utils.generate_default_name())

    @staticmethod
    def _get(conn, dataset_name=None, _dataset_id=None):
        if _dataset_id is not None:
            Message = _DatasetService.GetDatasetById
            msg = Message(id=_dataset_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/dataset/getDatasetById".format(conn.scheme, conn.socket),
                                           conn, params=data)

            if response.ok:
                dataset = _utils.json_to_proto(response.json(), Message.Response).dataset
                return dataset
            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    response.raise_for_status()
        else:
            raise ValueError("insufficient arguments")

    @staticmethod
    def _create(conn, dataset_name, dataset_type, desc=None, tags=None, attrs=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        Message = _DatasetService.CreateDataset
        msg = Message(name=dataset_name, dataset_type=dataset_type,
            description=desc, tags=tags, attributes=attrs)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/dataset/createDataset".format(conn.scheme, conn.socket),
                                       conn, json=data)

        if response.ok:
            dataset = _utils.json_to_proto(response.json(), Message.Response).dataset
            return dataset
        else:
            response.raise_for_status()


# TODO: visibility not done
# TODO: delete version not implemented

# from verta._protos.public.modeldb.DatasetVersionService_pb2 import \
#     DatasetVersion as DatasetVersionProtoCls


class DatasetVersion:
    def __init__(self, conn, conf, dataset_id=None, dataset_type=None,
        dataset_version_info=None, parent_id=None, desc=None, tags=None,
        attrs=None, version=None, _dataset_version_id=None):

        # retrieve dataset by id
        if _dataset_version_id is not None:
            dataset_version = DatasetVersion._get(conn, _dataset_version_id)
            if dataset_version is None:
                raise ValueError("DatasetVersion with ID {} not found".format(_dataset_version_id))
        else:
            if dataset_id is None:
                raise ValueError('dataset_id must be specified')

            # create a new dataset version
            try:
                dataset_version = DatasetVersion._create(conn, dataset_id,
                    dataset_type, dataset_version_info, parent_id=parent_id,
                    desc=desc, tags=tags, attrs=attrs, version=version)

            # TODO: handle dups
            except requests.HTTPError as e:
                # if e.response.status_code == 409:  # already exists
                #     if any(param is not None for param in (desc, tags, attrs)):
                #         warnings.warn("Dataset with name {} already exists;"
                #                         " cannot initialize `desc`, `tags`, or `attrs`".format(dataset_name))
                #     dataset_version = DatasetVersion._get(conn, dataset_id, version)
                # else:
                #     raise e
                raise e
            else:
                print("created new DatasetVersion: {}".format(
                    dataset_version.version))

        self._conn = conn
        self._conf = conf
        self.dataset_id = dataset_version.dataset_id

        # this info can be captured via a separate call too
        self.parent_id = dataset_version.parent_id
        self.desc = dataset_version.description
        self.tags = dataset_version.tags
        self.attrs = dataset_version.attributes
        self.id = dataset_version.id
        self.version = dataset_version.version
        self.dataset_type = dataset_version.dataset_type
        self.dataset_version = dataset_version
        self.dataset_version_info = None

    def __repr__(self):
        return "<DatasetVersion \"{}\">".format(self.id)

    # TODO: get by dataset_id and version is not supported on the backend
    @staticmethod
    def _get(conn, _dataset_version_id=None):
        if _dataset_version_id is not None:
            Message = _DatasetVersionService.GetDatasetVersionById
            msg = Message(id=_dataset_version_id)
            data = _utils.proto_to_json(msg)
            response = _utils.make_request("GET",
                                           "{}://{}/v1/dataset-version/getDatasetVersionById".format(conn.scheme, conn.socket),
                                           conn, params=data)

            if response.ok:
                dataset_version = _utils.json_to_proto(response.json(), Message.Response).dataset_version
                return dataset_version

            else:
                if response.status_code == 404 and response.json()['code'] == 5:
                    return None
                else:
                    response.raise_for_status()
        else:
            raise ValueError("insufficient arguments")

    @staticmethod
    def _create(conn, dataset_id, dataset_type, dataset_version_info,
        parent_id=None, desc=None, tags=None, attrs=None, version=None):
        if attrs is not None:
            attrs = [_CommonService.KeyValue(key=key, value=_utils.python_to_val_proto(value, allow_collection=True))
                     for key, value in six.viewitems(attrs)]

        if dataset_type == _DatasetService.DatasetTypeEnum.PATH:
            msg = PathDatasetVersion.make_create_message(dataset_id,
                dataset_type, dataset_version_info, parent_id=parent_id,
                desc=desc, tags=tags, attrs=attrs, version=version)
        elif dataset_type == _DatasetService.DatasetTypeEnum.QUERY:
            msg = QueryDatasetVersion.make_create_message(dataset_id,
                dataset_type, dataset_version_info, parent_id=parent_id,
                desc=desc, tags=tags, attrs=attrs, version=version)
        else:
            msg = RawDatasetVersion.make_create_message(dataset_id,
                dataset_type, dataset_version_info, parent_id=parent_id,
                desc=desc, tags=tags, attrs=attrs, version=version)

        data = _utils.proto_to_json(msg)
        response = _utils.make_request("POST",
                                       "{}://{}/v1/dataset-version/createDatasetVersion".format(conn.scheme, conn.socket),
                                       conn, json=data)

        if response.ok:
            dataset_version = _utils.json_to_proto(response.json(), _DatasetVersionService.CreateDatasetVersion.Response).dataset_version
            return dataset_version
        else:
            response.raise_for_status()

    @staticmethod
    def make_create_message(dataset_id, dataset_type, dataset_version_info,
        parent_id=None, desc=None, tags=None, attrs=None, version=None):
        raise NotImplementedError('Must be implemented by subclasses')


class RawDatasetVersion(DatasetVersion):
    def __init__(self, args, kwargs):
        super(RawDatasetVersion, self).__init__(*args, **kwargs)
        self.dataset_version_info = self.dataset_version.raw_dataset_version_info
        # TODO: this is hacky, we should store dataset_version
        self.dataset_version = None

    @staticmethod
    def make_create_message(dataset_id, dataset_type, dataset_version_info,
        parent_id=None, desc=None, tags=None, attrs=None, version=None):
        Message = _DatasetVersionService.CreateDatasetVersion
        version_msg =  _DatasetVersionService.RawDatasetVersionInfo
        converted_dataset_version_info = version_msg(
            size=dataset_version_info.size, features=dataset_version_info.features,
            num_records=dataset_version_info.num_records, object_path=dataset_version_info.object_path,
            checksum=dataset_version_info.checksum)
        msg = Message(dataset_id=dataset_id, parent_id=parent_id,
            description=desc, tags=tags, dataset_type=dataset_type,
            attributes=attrs, version=version,
            raw_dataset_version_info=converted_dataset_version_info)
        return msg


class QueryDatasetVersion(DatasetVersion):
    def __init__(self, *args, **kwargs):
        super(QueryDatasetVersion, self).__init__(*args, **kwargs)
        self.dataset_version_info = self.dataset_version.query_dataset_version_info
        # TODO: this is hacky, we should store dataset_version
        self.dataset_version = None

    @staticmethod
    def make_create_message(dataset_id, dataset_type, dataset_version_info,
        parent_id=None, desc=None, tags=None, attrs=None, version=None):
        Message = _DatasetVersionService.CreateDatasetVersion
        version_msg =  _DatasetVersionService.QueryDatasetVersionInfo
        converted_dataset_version_info = version_msg(
            query=dataset_version_info.query, query_template=dataset_version_info.query_template,
            query_parameters=dataset_version_info.query_parameters, data_source_uri=dataset_version_info.data_source_uri,
            execution_timestamp=dataset_version_info.execution_timestamp, num_records=dataset_version_info.num_records
        )
        msg = Message(dataset_id=dataset_id, parent_id=parent_id,
            description=desc, tags=tags, dataset_type=dataset_type,
            attributes=attrs, version=version,
            # different dataset versions
            query_dataset_version_info=converted_dataset_version_info)
        return msg


class PathDatasetVersion(DatasetVersion):
    def __init__(self, *args, **kwargs):
        super(PathDatasetVersion, self).__init__(*args, **kwargs)
        self.dataset_version_info = self.dataset_version.path_dataset_version_info
        # TODO: this is hacky, we should store dataset_version
        self.dataset_version = None

    @staticmethod
    def make_create_message(dataset_id, dataset_type, dataset_version_info,
        parent_id=None, desc=None, tags=None, attrs=None, version=None):
        Message = _DatasetVersionService.CreateDatasetVersion
        # turn dataset_version_info into proto format
        version_msg = _DatasetVersionService.PathDatasetVersionInfo
        converted_dataset_version_info = version_msg(
            location_type=dataset_version_info.location_type,
            size=dataset_version_info.size,
            dataset_part_infos=dataset_version_info.dataset_part_infos,
            base_path=dataset_version_info.base_path
        )
        msg = Message(dataset_id=dataset_id, parent_id=parent_id,
            description=desc, tags=tags, dataset_type=dataset_type,
            attributes=attrs, version=version,
            path_dataset_version_info=converted_dataset_version_info)
        return msg


class PathDatasetVersionInfo:
    def __init__(self):
        pass

    def compute_dataset_size(self):
        self.size = 0
        for dataset_part_info in self.dataset_part_infos:
            self.size += dataset_part_info.size

    def get_dataset_part_infos(self):
        raise NotImplementedError('Implemented only in subclasses')


class FilesystemDatasetVersionInfo(PathDatasetVersionInfo):
    def __init__(self, path):
        self.base_path = os.path.abspath(path)
        super(FilesystemDatasetVersionInfo, self).__init__()
        self.location_type = _DatasetVersionService.PathLocationTypeEnum.LOCAL_FILE_SYSTEM
        self.dataset_part_infos = self.get_dataset_part_infos()
        self.compute_dataset_size()

    def get_dataset_part_infos(self):
        dataset_part_infos = []
        # find all files there and create dataset_part_infos
        if os.path.isdir(self.base_path):
            dir_infos = os.walk(self.base_path)
            for root, _, filenames in dir_infos:
                for filename in filenames:
                    dataset_part_infos.append(self.get_file_info(root + "/" + filename))
        else:
            dataset_part_infos.append(self.get_file_info(self.base_path))
        # raise NotImplementedError('Only local files or S3 supported')
        return dataset_part_infos

    def get_file_info(self, path):
        dataset_part_info = _DatasetVersionService.DatasetPartInfo()
        dataset_part_info.path = path
        dataset_part_info.size = os.path.getsize(path)
        dataset_part_info.checksum = self.compute_file_hash(path)
        dataset_part_info.last_modified_at_source = int(os.path.getmtime(path))
        return dataset_part_info

    def compute_file_hash(self, path):
        BLOCKSIZE = 65536
        hasher = hashlib.md5()
        with open(path, 'rb') as afile:
            buf = afile.read(BLOCKSIZE)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(BLOCKSIZE)
        return hasher.hexdigest()


class S3DatasetVersionInfo(PathDatasetVersionInfo):
    def __init__(self, bucket_name, key=None, url_stub=None):
        super(S3DatasetVersionInfo, self).__init__()
        self.location_type = _DatasetVersionService.PathLocationTypeEnum.S3_FILE_SYSTEM
        self.bucket_name = bucket_name
        self.key = key
        self.url_stub = url_stub
        self.base_path = ("" if url_stub is None else url_stub) + bucket_name \
            + (("/" + key) if key is not None else "")
        self.dataset_part_infos = self.get_dataset_part_infos()
        self.compute_dataset_size()

    def get_dataset_part_infos(self):
        dataset_part_infos = []
        conn = BotoClient('s3')
        if self.key is None:
            for obj in conn.list_objects(Bucket=self.bucket_name)['Contents']:
                dataset_part_infos.append(self.get_s3_object_info(obj))
        else:
            obj = conn.head_object(Bucket=self.bucket_name, Key=self.key)
            dataset_part_infos.append(self.get_s3_object_info(obj, self.key))
        return dataset_part_infos

    @staticmethod
    def get_s3_object_info(object_info, key=None):
        # S3 also provides version info that could be used: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
        dataset_part_info = _DatasetVersionService.DatasetPartInfo()
        dataset_part_info.path = object_info['Key'] if key is None else key
        dataset_part_info.size = object_info['Size'] if key is None else object_info['ContentLength']
        dataset_part_info.checksum = object_info['ETag']
        dataset_part_info.last_modified_at_source = int((object_info['LastModified'] - \
            datetime.datetime(1970,1,1, tzinfo=pytz.UTC)).total_seconds())
        return dataset_part_info


class QueryDatasetVersionInfo:
    def __init__(self, job_id=None, query="", execution_timestamp="",
        data_source_uri="", query_template="", query_parameters=[],
        num_records=0):
        if not query:
            raise ValueError("query not found")
        self.query = query
        self.execution_timestamp = execution_timestamp
        self.data_source_uri = data_source_uri
        self.query_template = query_template
        self.query_parameters = query_parameters
        self.num_records = num_records


class BigQueryDatasetVersionInfo(QueryDatasetVersionInfo):
    def __init__(self, job_id=None, query="", location="", execution_timestamp="",
        data_source_uri="",query_template="",query_parameters=[],num_records=0):
        """https://googleapis.github.io/google-cloud-python/latest/bigquery/generated/google.cloud.bigquery.job.QueryJob.html#google.cloud.bigquery.job.QueryJob.query_plan"""
        if job_id is not None and location:
            self.job_id = job_id
            job = self.get_bq_job(job_id, location)
            self.execution_timestamp = int((job.started - datetime.datetime(1970,1,1, tzinfo=pytz.UTC)).total_seconds())
            self.data_source_uri = job.self_link
            self.query = job.query
            #TODO: extract the query template
            self.query_template = job.query
            self.query_parameters = []
            shape = job.to_dataframe().shape
            self.num_records = shape[0]
        else:
            super(BigQueryDatasetVersionInfo, self).__init__()

    @staticmethod
    def get_bq_job(job_id, location):
        client = bigquery.Client()
        return client.get_job(job_id, location = location)


class _ModelDBEntity:
    def __init__(self, conn, conf, service_module, service_url_component, id):
        self._conn = conn
        self._conf = conf

        self._service = service_module
        self._request_url = "{}://{}/v1/{}/{}".format(self._conn.scheme,
                                                      self._conn.socket,
                                                      service_url_component,
                                                      '{}')  # endpoint placeholder

        self.id = id

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
        response.raise_for_status()

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

            msg.code_version.code_archive.path = hashlib.sha256(zipstream.read()).hexdigest()
            zipstream.seek(0)
            msg.code_version.code_archive.path_only = False
            msg.code_version.code_archive.artifact_type = _CommonService.ArtifactTypeEnum.CODE
            msg.code_version.code_archive.filename_extension = 'zip'
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
                response.raise_for_status()

        if msg.code_version.WhichOneof("code") == 'code_archive':
            # upload artifact to artifact store
            url = self._get_url_for_artifact("verta_code_archive", "PUT", msg.code_version.code_archive.artifact_type)
            response = _utils.make_request("PUT", url, self._conn, data=zipstream)
            response.raise_for_status()

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
        response.raise_for_status()

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
            response.raise_for_status()

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
                                       "{}://{}/v1/experiment-run/getExperimentRunsInProject".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        response.raise_for_status()

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
                    response.raise_for_status()
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
                    response.raise_for_status()
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
            response.raise_for_status()


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
                                       "{}://{}/v1/experiment-run/getExperimentRunsInExperiment".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        response.raise_for_status()

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
                response.raise_for_status()

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
    _OP_MAP = {'==': _CommonService.OperatorEnum.EQ,
               '!=': _CommonService.OperatorEnum.NE,
               '>':  _CommonService.OperatorEnum.GT,
               '>=': _CommonService.OperatorEnum.GTE,
               '<':  _CommonService.OperatorEnum.LT,
               '<=': _CommonService.OperatorEnum.LTE}
    _OP_PATTERN = re.compile(r"({})".format('|'.join(sorted(six.viewkeys(_OP_MAP), key=lambda s: len(s), reverse=True))))

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
        >>> runs.find(["hyperparameters.hidden_size == 256",
        ...            "metrics.accuracy >= .8"])
        <ExperimentRuns containing 3 runs>

        """
        if _proj_id is not None and _expt_id is not None:
            raise ValueError("cannot specify both `_proj_id` and `_expt_id`")
        elif _proj_id is None and _expt_id is None:
            if self.__len__() == 0:
                return self.__class__(self._conn)
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
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._conn, self._conf, [expt_run.id for expt_run in response_msg.experiment_runs])

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
            return self.__class__(self._conn)

        Message = _ExperimentRunService.SortExperimentRuns
        msg = Message(experiment_run_ids=self._ids,
                      sort_key=key, ascending=not descending, ids_only=not ret_all_info)
        data = _utils.proto_to_json(msg)
        response = _utils.make_request("GET",
                                       "{}://{}/v1/experiment-run/sortExperimentRuns".format(self._conn.scheme, self._conn.socket),
                                       self._conn,
                                       params=data)
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._conn, self._conf, [expt_run.id for expt_run in response_msg.experiment_runs])

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
                return self.__class__(self._conn)
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
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        if ret_all_info:
            return response_msg.experiment_runs
        else:
            return self.__class__(self._conn, self._conf, [expt_run.id for expt_run in response_msg.experiment_runs])

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
                return self.__class__(self._conn)
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
        response.raise_for_status()

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
        response.raise_for_status()

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
        response.raise_for_status()

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
                response.raise_for_status()

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
            response.raise_for_status()

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
                response.raise_for_status()

        # upload artifact to artifact store
        url = self._get_url_for_artifact(key, "PUT")
        artifact_stream.seek(0)  # reuse stream that was created for checksum
        if self._conf.debug:
            print("[DEBUG] uploading {} bytes ({})".format(len(artifact_stream.read()), basename))
            artifact_stream.seek(0)
        response = _utils.make_request("PUT", url, self._conn, data=artifact_stream)
        response.raise_for_status()
        print("upload complete ({})".format(basename))

    def _log_artifact_path(self, key, artifact_path, artifact_type, linked_artifact_id=None):
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
        # TODO: this design might need to be revisited by @miliu
        linked_artifact_id: string, optional
            Id of linked artifact
        """
        # log key-path to ModelDB
        Message = _ExperimentRunService.LogArtifact
        artifact_msg = _CommonService.Artifact(key=key,
                                               path=artifact_path,
                                               path_only=True,
                                               artifact_type=artifact_type,
                                               linked_artifact_id=linked_artifact_id)
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
                response.raise_for_status()


    def _log_dataset_path(self, key, dataset_path, linked_artifact_id=None):
        """
        Logs the filesystem path of an artifact to this Experiment Run.

        Parameters
        ----------
        key : str
            Name of the artifact.
        artifact_path : str
            Filesystem path of the artifact.
        # TODO: this design might need to be revisited by @miliu
        linked_artifact_id: string, optional
            Id of linked artifact
        """
        # log key-path to ModelDB
        Message = _ExperimentRunService.LogDataset
        artifact_msg = _CommonService.Artifact(key=key,
                                               path=dataset_path,
                                               path_only=True,
                                               artifact_type=_CommonService.ArtifactTypeEnum.DATA,
                                               linked_artifact_id=linked_artifact_id)
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
                                       "{}://{}/v1/experiment-run/getArtifacts".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
            response = _utils.make_request("GET", url, self._conn)
            response.raise_for_status()

            return response.content, artifact.path_only

    # TODO: fix up get dataset to handle the Dataset class
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
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        dataset = {dataset.key: dataset for dataset in response_msg.datasets}.get(key)
        if dataset is None:
            raise KeyError("no dataset found with key {}".format(key))
        if dataset.path_only:
            return dataset.path, dataset.path_only, dataset.linked_artifact_id
        else:
            raise NotImplementedError("Temporary hack")
            # # download dataset from artifact store
            # url = self._get_url_for_dataset(key, "GET")
            # response = _utils.make_request("GET", url, self._conn)
            # response.raise_for_status()

            # return response.content, dataset.path_only, None

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
                                       "{}://{}/v1/experiment-run/addExperimentRunTags".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/addExperimentRunTags".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/getExperimentRunTags".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
                                       "{}://{}/v1/experiment-run/logAttribute".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/logAttributes".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/getAttributes".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
                                       "{}://{}/v1/experiment-run/getAttributes".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
                                       "{}://{}/v1/experiment-run/logMetric".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/logMetrics".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/getMetrics".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
                                       "{}://{}/v1/experiment-run/getMetrics".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
                                       "{}://{}/v1/experiment-run/logHyperparameter".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/logHyperparameters".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/getHyperparameters".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
                                       "{}://{}/v1/experiment-run/getHyperparameters".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
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
                - If type is Dataset, then it will log a dataset version
                - Otherwise, the object will be serialized and uploaded as an artifact.

        """
        _utils.validate_flat_key(key)

        if isinstance(dataset, Dataset):
            pass
            # version = self.create_dataset_version()
            # self._log_dataset(key, dataset, ...)
        else:
            try:
                extension = _artifact_utils.get_file_ext(dataset)
            except (TypeError, ValueError):
                extension = None

            self._log_artifact(key, dataset, _CommonService.ArtifactTypeEnum.DATA, extension)

    def log_dataset_version(self, key, dataset_version):
        # TODO: hack because path_only artifact needs a placeholder path
        if not isinstance(dataset_version, DatasetVersion):
            raise ValueError('dataset_version should be of type DatasetVersion')
        self.log_dataset_path(key, "See attached dataset version", dataset_version.id)

    def log_dataset_path(self, key, path, linked_dataset_id=None):
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

        self._log_dataset_path(key, path, linked_artifact_id=linked_dataset_id)

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
            If of dataset type, then return a version_id
            Filesystem path of the dataset, the dataset object, or a bytestream representing the
            dataset.

        """
        dataset, path_only, linked_id = self._get_dataset(key)
        if path_only:
            return dataset, linked_id
        else:
            # TODO: may need to be updated for raw
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
        if self._conf.debug:
            if not hasattr(model, 'read'):
                print("[DEBUG] model is type: {}".format(model.__class__))
        _artifact_utils.reset_stream(model)  # reset cursor to beginning in case user forgot
        try:
            model_extension = _artifact_utils.get_file_ext(model)
        except (TypeError, ValueError):
            model_extension = None
        model, method, model_type, expand_arguments = _artifact_utils.serialize_model(model)
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
                'expand_arguments': expand_arguments,
            }
        if self._conf.debug:
            print("[DEBUG] model API is:")
            pprint.pprint(model_api.to_dict())

        # prehandle requirements
        _artifact_utils.reset_stream(requirements)  # reset cursor to beginning in case user forgot
        _artifact_utils.validate_requirements_txt(requirements)
        if method == "cloudpickle":  # if cloudpickle used, add to requirements
            cloudpickle_dep = "cloudpickle=={}".format(_artifact_utils.cloudpickle.__version__)
            req_deps = six.ensure_str(requirements.read()).splitlines()
            _artifact_utils.reset_stream(requirements)  # reset cursor to beginning as a courtesy
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

        model, method, _, _= _artifact_utils.serialize_model(model)

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
                                       "{}://{}/v1/experiment-run/logObservation".format(self._conn.scheme, self._conn.socket),
                                       self._conn, json=data)
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
                                       "{}://{}/v1/experiment-run/getObservations".format(self._conn.scheme, self._conn.socket),
                                       self._conn, params=data)
        response.raise_for_status()

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
        response.raise_for_status()

        response_msg = _utils.json_to_proto(response.json(), Message.Response)
        return _utils.unravel_observations(response_msg.experiment_run.observations)

    def log_modules(self, paths, search_path=None):
        """
        Logs local files that are dependencies for a deployed model to this Experiment Run.

        Parameters
        ----------
        paths : str or list of str
            Paths to local Python modules and other files that the deployed model depends on. If a
            directory is provided, all files within will be included.

        """
        if search_path is not None:
            warnings.warn("`search_path` is no longer used and will removed in a later version;"
                          " consider removing it from the function call",
                          category=DeprecationWarning, stacklevel=2)
        if isinstance(paths, six.string_types):
            paths = [paths]

        # convert into absolute paths
        paths = map(os.path.abspath, paths)
        # add trailing separator to directories
        paths = [os.path.join(path, "") if os.path.isdir(path) else path
                 for path in paths]

        # obtain deepest common directory
        curr_dir = os.path.join(os.path.abspath(os.curdir), "")
        paths_plus = paths + [curr_dir]
        common_prefix = os.path.commonprefix(paths_plus)
        common_dir = os.path.dirname(common_prefix)

        filepaths = _utils.find_filepaths(paths, include_hidden=True)

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
        search_paths = list(map(lambda path: os.path.join("/app/custom_modules/", path), search_paths))
        if self._conf.debug:
            print("[DEBUG] deployment search paths are:")
            pprint.pprint(search_paths)

        bytestream = six.BytesIO()
        with zipfile.ZipFile(bytestream, 'w') as zipf:
            for filepath in filepaths:
                zipf.write(filepath, os.path.relpath(filepath, common_dir))
            zipf.writestr(
                "_verta_config.py",
                six.ensure_binary('\n'.join([
                    "import sys",
                    "",
                    "sys.path = sys.path[:1] + {} + sys.path[1:]".format(list(search_paths)),
                ]))
            )
            if self._conf.debug:
                print("[DEBUG] archive contains:")
                zipf.printdir()
        bytestream.seek(0)

        self._log_artifact("custom_modules", bytestream, _CommonService.ArtifactTypeEnum.BLOB, 'zip')
