import six

import json
import numbers
import os
import string
import time

from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value, NULL_VALUE


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
    return json_format.Parse(json.dumps(response_json), response_cls())


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
        raise ValueError("unsupported type {}; consider using log_artifact() instead".format(type(val)))


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
    return "{}{}".format(os.getpid(), str(time.time()).replace('.', ''))
