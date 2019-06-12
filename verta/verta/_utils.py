import six

from datetime import datetime
import json
import numbers
import os
import string
import subprocess
import sys

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value, ListValue, Struct, NULL_VALUE

from ._protos.public.modeldb import CommonService_pb2 as _CommonService

try:
    import pandas as pd
except ImportError:  # pandas not installed
    pass


_VALID_HTTP_METHODS = {'GET', 'POST', 'PUT', 'DELETE'}
_VALID_FLAT_KEY_CHARS = set(string.ascii_letters + string.digits + '_-')


class Connection:
    def __init__(self, scheme=None, socket=None, auth=None, max_retries=0, ignore_conn_err=False):
        """
        HTTP connection configuration utility struct.

        Parameters
        ----------
        scheme : {'http', 'https'}, optional
            HTTP authentication scheme.
        socket : str, optional
            Hostname and port.
        auth : dict, optional
            Verta authentication headers.
        max_retries : int, default 0
            Maximum number of times to retry a request on a connection failure. This only attempts retries
            on HTTP codes {403, 503, 504} which commonly occur during back end connection lapses.
        ignore_conn_err : bool, default False
            Whether to ignore connection errors and instead return successes with empty contents.

        """
        self.scheme = scheme
        self.socket = socket
        self.auth = auth
        # TODO: retry on 404s, but only if we're sure it's not legitimate e.g. from a GET
        self.retry = Retry(total=max_retries,
                           backoff_factor=1,  # each retry waits (2**retry_num) seconds
                           method_whitelist=False,  # retry on all HTTP methods
                           status_forcelist=(403, 503, 504),  # only retry on these status codes
                           raise_on_redirect=False,  # return Response instead of raising after max retries
                           raise_on_status=False)  # return Response instead of raising after max retries
        self.ignore_conn_err = ignore_conn_err


def make_request(method, url, conn, **kwargs):
    """
    Makes a REST request.

    Parameters
    ----------
    method : {'GET', 'POST', 'PUT', 'DELETE'}
        HTTP method.
    url : str
        URL.
    conn : verta._utils.Connection
        Connection authentication and configuration.
    **kwargs
        Parameters to requests.request().

    Returns
    -------
    requests.Response

    """
    if method.upper() not in _VALID_HTTP_METHODS:
        raise ValueError("`method` must be one of {}".format(_VALID_HTTP_METHODS))

    if conn.auth is not None:
        # add auth to `kwargs['headers']`
        kwargs.setdefault('headers', {}).update(conn.auth)

    with requests.Session() as s:
        s.mount(url, HTTPAdapter(max_retries=conn.retry))
        try:
            response = s.request(method, url, **kwargs)
        except (requests.exceptions.BaseHTTPError,
                requests.exceptions.RequestException) as e:
            if not conn.ignore_conn_err:
                raise e
        else:
            if response.ok or not conn.ignore_conn_err:
                return response
        # fabricate response
        response = requests.Response()
        response.status_code = 200  # success
        response._content = six.ensure_binary("{}")  # empty contents
        return response


def find_filepaths(paths, extensions, include_hidden=False):
    """
    Unravels a list of file and directory paths into a list of only filepaths by walking through the
    directories.

    Parameters
    ----------
    paths : str or list of str
        File and directory paths.
    extensions : str or list of str
        What files to include while walking through directories.
    include_hidden : bool, default False
        Whether to include hidden files and subdirectories found while walking through directories.

    """
    if isinstance(paths, six.string_types):
        paths = [paths]
    # convert into absolute paths
    paths = map(os.path.abspath, paths)

    if isinstance(extensions, six.string_types):
        extensions = [extensions]
    # prepend period to file extensions where missing
    extensions = map(lambda ext: ext if ext.startswith('.') else ".{}".format(ext), extensions)
    extensions = set(extensions)

    filepaths = []
    for path in paths:
        if os.path.isdir(path):
            for root, _, subpaths in os.walk(path):
                if os.path.basename(root).startswith('.') and not include_hidden:
                    continue
                for subpath in subpaths:
                    if os.path.basename(subpath).startswith('.') and not include_hidden:
                        continue
                    if os.path.splitext(subpath)[1] in extensions:
                        filepaths.append(os.path.join(root, subpath))
        else:
            filepaths.append(path)
    return filepaths


def proto_to_json(msg):
    """
    Converts a `protobuf` `Message` object into a JSON-compliant dictionary.

    The output preserves snake_case field names and integer representaions of enum variants.

    Parameters
    ----------
    msg : google.protobuf.message.Message
        `protobuf` `Message` object.

    Returns
    -------
    dict
        JSON object representing `msg`.

    """
    return json.loads(json_format.MessageToJson(msg,
                                                including_default_value_fields=True,
                                                preserving_proto_field_name=True,
                                                use_integers_for_enums=True))


def json_to_proto(response_json, response_cls):
    """
    Converts a JSON-compliant dictionary into a `protobuf` `Message` object.

    Parameters
    ----------
    response_json : dict
        JSON object representing a Protocol Buffer message.
    response_cls : type
        `protobuf` `Message` subclass, e.g. ``CreateProject.Response``.

    Returns
    -------
    google.protobuf.message.Message
        `protobuf` `Message` object represented by `response_json`.

    """
    return json_format.Parse(json.dumps(response_json),
                             response_cls(),
                             ignore_unknown_fields=True)


def python_to_val_proto(val, allow_collection=False):
    """
    Converts a Python variable into a `protobuf` `Value` `Message` object.

    Parameters
    ----------
    val : one of {None, bool, float, int, str, list, dict}
        Python variable.
    allow_collection : bool, default False
        Whether to allow ``list``s and ``dict``s as `val`. This flag exists because some callers
        ought to not support logging collections, so this function will perform the typecheck on `val`.

    Returns
    -------
    google.protobuf.struct_pb2.Value
        `protobuf` `Value` `Message` representing `val`.

    """
    if val is None:
        return Value(null_value=NULL_VALUE)
    elif isinstance(val, bool):  # did you know that `bool` is a subclass of `int`?
        return Value(bool_value=val)
    elif isinstance(val, numbers.Real):
        return Value(number_value=val)
    elif isinstance(val, six.string_types):
        return Value(string_value=val)
    elif isinstance(val, (list, dict)):
        if allow_collection:
            if isinstance(val, list):
                list_value = ListValue()
                list_value.extend(val)
                return Value(list_value=list_value)
            else:  # isinstance(val, dict)
                if all([isinstance(key, six.string_types) for key in val.keys()]):
                    struct_value = Struct()
                    struct_value.update(val)
                    return Value(struct_value=struct_value)
                else:  # protobuf's fault
                    raise TypeError("struct keys must be strings; consider using log_artifact() instead")
        else:
            raise TypeError("unsupported type {}; consider using log_attribute() instead".format(type(val)))
    else:
        raise TypeError("unsupported type {}; consider using log_artifact() instead".format(type(val)))


def val_proto_to_python(msg):
    """
    Converts a `protobuf` `Value` `Message` object into a Python variable.

    Parameters
    ----------
    msg : google.protobuf.struct_pb2.Value
        `protobuf` `Value` `Message` representing a variable.

    Returns
    -------
    one of {None, bool, float, int, str}
        Python variable represented by `msg`.

    """
    value_kind = msg.WhichOneof("kind")
    if value_kind == "null_value":
        return None
    elif value_kind == "bool_value":
        return msg.bool_value
    elif value_kind == "number_value":
        return int(msg.number_value) if msg.number_value.is_integer() else msg.number_value
    elif value_kind == "string_value":
        return msg.string_value
    elif value_kind == "list_value":
        return [val_proto_to_python(val_msg)
                for val_msg
                in msg.list_value.values]
    elif value_kind == "struct_value":
        return {key: val_proto_to_python(val_msg)
                for key, val_msg
                in msg.struct_value.fields.items()}
    else:
        raise NotImplementedError("retrieved value type is not supported")


def unravel_key_values(rpt_key_value_msg):
    """
    Converts a repeated KeyValue field of a protobuf message into a dictionary.

    Parameters
    ----------
    rpt_key_value_msg : google.protobuf.pyext._message.RepeatedCompositeContainer
        Repeated KeyValue field of a protobuf message.

    Returns
    -------
    dict of str to {None, bool, float, int, str}
        Names and values.

    """
    return {key_value.key: val_proto_to_python(key_value.value)
            for key_value
            in rpt_key_value_msg}


def unravel_artifacts(rpt_artifact_msg):
    """
    Converts a repeated Artifact field of a protobuf message into a list of names.

    Parameters
    ----------
    rpt_artifact_msg : google.protobuf.pyext._message.RepeatedCompositeContainer
        Repeated Artifact field of a protobuf message.

    Returns
    -------
    list of str
        Names of artifacts.

    """
    return [artifact.key
            for artifact
            in rpt_artifact_msg]


def unravel_observation(obs_msg):
    """
    Converts an Observation protobuf message into a more straightforward Python tuple.

    This is useful because an Observation message has a oneof that's finicky to handle.

    Returns
    -------
    str
        Name of observation.
    {None, bool, float, int, str}
        Value of observation.
    str
        Human-readable timestamp.

    """
    if obs_msg.WhichOneof("oneOf") == "attribute":
        key = obs_msg.attribute.key
        value = obs_msg.attribute.value
    elif obs_msg.WhichOneof("oneOf") == "artifact":
        key = obs_msg.artifact.key
        value = "{} artifact".format(_CommonService.ArtifactTypeEnum.ArtifactType.Name(obs_msg.artifact.artifact_type))
    return (
        key,
        val_proto_to_python(value),
        timestamp_to_str(obs_msg.timestamp),
    )


def unravel_observations(rpt_obs_msg):
    """
    Converts a repeated Observation field of a protobuf message into a dictionary.

    Parameters
    ----------
    rpt_obs_msg : google.protobuf.pyext._message.RepeatedCompositeContainer
        Repeated Observation field of a protobuf message.

    Returns
    -------
    dict of str to list of tuples ({None, bool, float, int, str}, str)
        Names and observation sequences.

    """
    observations = {}
    for obs_msg in rpt_obs_msg:
        key, value, timestamp = unravel_observation(obs_msg)
        observations.setdefault(key, []).append((value, timestamp))
    return observations


def validate_flat_key(key):
    """
    Checks whether `key` contains invalid characters.

    To prevent bugs with querying (which allow dot-delimited nested keys), flat keys (such as those
    used for individual metrics) must not contain periods.

    Furthermore, to prevent potential bugs with the back end down the line, keys should be restricted
    to alphanumeric characters, underscores, and dashes until we can verify robustness.

    Parameters
    ----------
    key : str
        Name of metadatum.

    Raises
    ------
    ValueError
        If `key` contains invalid characters.

    """
    for c in key:
        if c not in _VALID_FLAT_KEY_CHARS:
            raise ValueError("`key` may only contain alphanumeric characters, underscores, and dashes")


def generate_default_name():
    """
    Generates a string that can be used as a default entity name while avoiding collisions.

    The generated string is a concatenation of the current process ID and the current Unix timestamp,
    such that a collision should only occur if a single process produces two of an entity at the same
    nanosecond.

    Returns
    -------
    name : str
        String generated from the current process ID and Unix timestamp.

    """
    return "{}{}".format(os.getpid(), str(to_timestamp(datetime.now())).replace('.', ''))


def to_timestamp(dt):
    """
    Converts a datetime instance into a Unix timestamp.

    Equivalent to Python 3's ``dt.timestamp()`` on a naive datetime instance.

    Parameters
    ----------
    dt : datetime.datetime
        datetime instance.

    Returns
    -------
    float
        Unix timestamp.

    """
    return (dt - datetime.fromtimestamp(0)).total_seconds()


def timestamp_to_ms(timestamp):
    """
    Converts a Unix timestamp into one with millisecond resolution.

    Parameters
    ----------
    timestamp : float or int
        Unix timestamp.

    Returns
    -------
    int
        `timestamp` with millisecond resolution (13 integer digits).

    """
    num_integer_digits = len(str(timestamp).split('.')[0])
    return int(timestamp*10**(13 - num_integer_digits))


def ensure_timestamp(timestamp):
    """
    Converts a representation of a datetime into a Unix timestamp with millisecond resolution.

    If `timestamp` is provided as a string, this function attempts to use pandas (if installed) to
    parse it into a Unix timestamp, since pandas can interally handle many different human-readable
    datetime string representations. If pandas is not installed, this function will only handle an
    ISO 8601 representation.

    Parameters
    ----------
    timestamp : str or float or int
        String representation of a datetime or numerical Unix timestamp.

    Returns
    -------
    int
        `timestamp` with millisecond resolution (13 integer digits).

    """
    if isinstance(timestamp, six.string_types):
        try:  # attempt with pandas, which can parse many time string formats
            return timestamp_to_ms(pd.Timestamp(timestamp).timestamp())
        except NameError:  # pandas not installed
            try:  # fall back on std lib, and parse as ISO 8601
                timestamp_to_ms(to_timestamp(datetime.fromisoformat(timestamp)))
            except ValueError:
                six.raise_from(ValueError("`timestamp` must be in ISO 8601 format,"
                                          " e.g. \"2017-10-30T00:44:16+00:00\""),
                               None)
        except ValueError:  # can't be handled by pandas
            six.raise_from(ValueError("unable to parse datetime string \"{}\"".format(timestamp)),
                           None)
    elif isinstance(timestamp, numbers.Real):
        return timestamp_to_ms(timestamp)
    else:
        raise TypeError("unable to parse timestamp of type {}".format(type(timestamp)))


def timestamp_to_str(timestamp):
    """
    Converts a Unix timestamp into a human-readable string representation.

    Parameters
    ----------
    timestamp : int
        Numerical Unix timestamp.

    Returns
    -------
    str
        Human-readable string representation of `timestamp`.

    """
    num_digits = len(str(timestamp))
    return str(datetime.fromtimestamp(timestamp*10**(10 - num_digits)))


def now():
    """
    Returns the current Unix timestamp with millisecond resolution.

    Returns
    -------
    now : int
        Current Unix timestamp in milliseconds.

    """
    return timestamp_to_ms(to_timestamp(datetime.now()))


def get_python_version():
    """
    Returns the version number of the locally-installed Python interpreter.

    Returns
    -------
    str
        Python version number in the form "{major}.{minor}.{patch}".

    """
    return '.'.join(map(str, sys.version_info[:3]))


def get_git_commit_hash():
    try:
        return six.ensure_str(
            subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"])
        ).strip()
    except:
        pass
    raise OSError("unable to find git commit hash")


def get_git_commit_dirtiness():
    try:
        diff_paths = six.ensure_str(
            subprocess.check_output(["git", "status", "--porcelain"])
        ).splitlines()
    except:
        pass
    else:
        return not all(path.startswith("??") for path in diff_paths)
    raise OSError("unable to find git status")


def get_git_remote_url():
    try:
        return six.ensure_str(
            subprocess.check_output(["git", "ls-remote", "--get-url"])
        ).strip()
    except:
        pass
    raise OSError("unable to find git remote URL")


def get_git_branch_name():
    try:
        return six.ensure_str(
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        ).strip()
    except:
        pass
    raise OSError("unable to find git branch name")


def get_git_repo_root_dir():
    try:
        dirpath = six.ensure_str(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
        ).strip()
    except:
        pass
    else:
        # append trailing separator
        return os.path.join(dirpath, "")
    raise OSError("unable to find git repository root directory")


# TODO: support pip3 and conda
# def get_env_dependencies():
#     """
#     Returns a list of packages present in the current Python environment.

#     Returns
#     -------
#     dependencies : list of str
#         Names of packages and their pinned version numbers in the current Python environment.

#     """
#     return six.ensure_str(subprocess.check_output(["pip", "freeze"])).splitlines()
