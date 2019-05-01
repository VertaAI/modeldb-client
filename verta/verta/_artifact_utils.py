import six
import six.moves.cPickle as pickle

from verta import _utils

try:
    from tensorflow import keras
except ImportError:
    pass


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
    if hasattr(obj, 'read'):  # if `obj` is file-like
        try:  # reset cursor to beginning in case user forgot
            obj.seek(0)
        except AttributeError:
            pass
        contents = obj.read()  # read to cast into binary
        try:  # reset cursor to beginning as a courtesy
            obj.seek(0)
        except AttributeError:
            pass
        if not len(contents):
            raise ValueError("object contains no data")
        bytestring = six.ensure_binary(contents)
    else:  # `obj` is not file-like
        bytestring = pickle.dumps(obj)
    return six.BytesIO(bytestring)


def serialize_model(model):
    """
    Serializes a model into a bytestream, attempting various methods.

    Parameters
    ----------
    model : object or file-like
        Model to convert into a bytestream.

    Returns
    -------
    file-like
        Buffered bytestream.

    """
    # try to use model-specific serializations
    bytestream = six.BytesIO()
    try:
        model.save(bytestream)
    except AttributeError:
        model = ensure_bytestream(model)
    else:
        bytestream.seek(0)
        model = bytestream

    return model


def deserialize_model(bytestring):
    """
    Deserializes a model from a bytestring, attempting various methods.

    If the model is unable to be deserialized, the bytes will be returned as a buffered bytestream.

    Parameters
    ----------
    bytestring : bytes
        Bytes representing the model.

    Returns
    -------
    model : obj or file-like
        Model or buffered bytestream representing the model.

    """
    bytestream = six.BytesIO(bytestring)
    try:
        return keras.models.load_model(bytestream)
    except NameError:  # Tensorflow not installed
        pass
    except OSError:  # not a Keras model
        pass
    try:
        return pickle.load(bytestream)
    except pickle.UnpicklingError:  # not a pickled object
        pass
    return bytestream
