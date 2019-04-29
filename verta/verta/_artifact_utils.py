import six

import pickle

try:
    from tensorflow import keras
except ImportError:
    pass


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
    bytestream : obj or file-like
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
