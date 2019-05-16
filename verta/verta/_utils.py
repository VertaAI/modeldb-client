import six

from datetime import datetime
import json
import numbers
import os
import string

from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value, NULL_VALUE

from ._protos.public.modeldb import CommonService_pb2 as _CommonService

try:
    import pandas as pd
except ImportError:  # pandas not installed
    pass


_VALID_FLAT_KEY_CHARS = set(string.ascii_letters + string.digits + '_-')


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


def python_to_val_proto(val):
    """
    Converts a Python variable into a `protobuf` `Value` `Message` object.

    Parameters
    ----------
    val : one of {None, bool, float, int, str}
        Python variable.

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
    if msg.HasField("null_value"):
        return None
    if msg.HasField("bool_value"):
        return msg.bool_value
    if msg.HasField("number_value"):
        number_value = msg.number_value
        if number_value.is_integer():
            return int(number_value)
        else:
            return number_value
    if msg.HasField("string_value"):
        return msg.string_value
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
    return "{}{}".format(os.getpid(), str(datetime.now().timestamp()).replace('.', ''))


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
                timestamp_to_ms(datetime.fromisoformat(timestamp).timestamp())
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
    return timestamp_to_ms(datetime.now().timestamp())
