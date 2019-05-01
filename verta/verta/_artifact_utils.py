import six

import pickle

from verta import _utils

try:
    from tensorflow import keras
except ImportError:
    pass


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
        model = _utils.ensure_bytestream(model)
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
