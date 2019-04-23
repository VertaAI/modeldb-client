import six
import six.moves.cPickle as pickle

import os
import pathlib2


def dump(obj, filename):
    """
    Serializes `obj` to disk at path `filename`.

    Recursively creates parent directories of `filename` if they do not already exist.

    Parameters
    ----------
    obj : object
        Object to be serialized.
    filename : str
        Path to which to write serialized `obj`.

    """
    # try to dump in current dir to confirm serializability
    temp_filename = '.' + os.path.basename(filename)
    while os.path.exists(temp_filename):  # avoid name collisions
        temp_filename += '_'
    pickle.dump(obj, temp_filename)

    # create parent directory
    dirpath = os.path.dirname(filename)  # get parent dir
    pathlib2.Path(dirpath).mkdir(parents=True, exist_ok=True)  # create parent dir

    # move file to `filename`
    os.rename(temp_filename, filename)


def load(filename):
    """
    Deserializes an object from disk at path `filename`.

    Parameters
    ----------
    filename : str
        Path to file containing serialized object.

    Returns
    -------
    obj : object
        Deserialized object.

    """
    return pickle.load(filename)
