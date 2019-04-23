import six
import six.moves.cPickle as pickle

import json
import string

from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value, NULL_VALUE


_VALID_FLAT_KEY_CHARS = set(string.ascii_letters + string.digits + '_')


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
    elif isinstance(val, float) or isinstance(val, six.integer_types):
        return Value(number_value=val)
    elif isinstance(val, six.string_types):
        return Value(string_value=val)
    elif isinstance(val, dict):
        raise NotImplementedError()
    elif isinstance(val, list):
        raise NotImplementedError()
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
    if msg.HasField("struct_value"):
        raise NotImplementedError()
    if msg.HasField("list_value"):
        raise NotImplementedError()
    else:
        raise ValueError("Value is empty")


def validate_flat_key(key):
    """
    Checks whether `key` contains invalid characters.

    To prevent bugs with querying (which allow dot-delimited nested keys), flat keys (such as those
    used for individual metrics) must not contain periods.

    Furthermore, to prevent potential bugs with the backend down the line, keys should be restricted
    to alphanumeric characters and underscores until we can verify robustness.

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
            raise ValueError("`key` may only contain alphanumeric characters and underscores")


def ensure_bytestream(obj):
    """
    Converts an object into a bytestream.

    If `obj` is file-like, its contents will be read into memory and then wrapped in a bytestream.
    This has a performance cost, but checking beforehand whether an arbitrary file-like object
    returns bytes is an implementation nightmare.

    If `obj` is not file-like, it will be serialized and then wrapped in a bytestream.

    Parameters
    ----------
    obj : file-like or object
        Object to convert into a bytestream.

    Returns
    -------
    file-like
        Buffered bytestream.

    Raises
    ------
    ValueError
        If `obj` contains no data.

    """
    if hasattr(obj, 'read'):  # check if `obj` is file-like
        try:  # reset cursor to beginning of stream in case user forgot
            obj.seek(0)
        except AttributeError:
            pass
        # read to cast into binary
        contents = obj.read()
        if not len(contents):
            raise ValueError("object contains no data")
        bytestring = six.ensure_binary(contents)
    else:  # `obj` is not file-like
        bytestring = pickle.dumps(obj)
    return six.BytesIO(bytestring)
