import six
import six.moves.cPickle as pickle

import collections
import json
import numbers
import os
import pathlib2


class ModelAPI:
    """
    A file-like and partially dict-like object representing a Verta model API.

    Parameters
    ----------
    x : {None, bool, int, float, str, dict, list}
        An archetypal input for the model this API describes.
    y : {None, bool, int, float, str, dict, list}
        An archetypal output for the model this API describes.

    Attributes
    ----------
    is_valid : bool
        Whether or not this Model API adheres to Verta's complete specification.

    """
    def __init__(self, x, y):
        self._buffer = six.StringIO(json.dumps({
            'version': "v1",
            'input': ModelAPI._data_to_api(x),
            'output': ModelAPI._data_to_api(y),
        }))

    def __str__(self):
        ptr_pos = self.tell()  # save current pointer position
        self.seek(0)
        contents = self.read()
        self.seek(ptr_pos)  # restore pointer position
        return contents

    def __setitem__(self, key, value):
        if self.tell():
            raise ValueError("pointer must be reset before setting an item; please use seek(0)")
        api_dict = json.loads(self.read())
        api_dict[key] = value
        self._buffer = six.StringIO(json.dumps(api_dict))

    def __contains__(self, key):
        return key in self.to_dict()

    @property
    def is_valid(self):
        raise NotImplementedError

    @staticmethod
    def _data_to_api(data, name=None):
        """
        Translates a Python value into an appropriate node for the model API.

        If the Python value is list-like or dict-like, its items will also be recursively translated.

        Parameters
        ----------
        data : {None, bool, int, float, str, dict, list}
            Python value.
        name : str, optional
            Name of the model API value node.

        Returns
        -------
        dict
            A model API value node.

        """
        if data is None:
            return {'type': "VertaNull",
                    'name': "some_null_value" if name is None else name}
        elif isinstance(data, bool):  # did you know that `bool` is a subclass of `int`?
            return {'type': "VertaBool",
                    'name': "some_boolean_value" if name is None else name}
        elif isinstance(data, numbers.Integral):
            return {'type': "VertaInt",
                    'name': "some_integer_value" if name is None else name}
        elif isinstance(data, numbers.Real):
            return {'type': "VertaFloat",
                    'name': "some_float_value" if name is None else name}
        elif isinstance(data, six.string_types):
            return {'type': "VertaString",
                    'name': "some_string_value" if name is None else name}
        elif isinstance(data, collections.Mapping):
            return {'type': "VertaJson",
                    'name': "some_json_value",
                    'value': [ModelAPI._data_to_api(value, str(name)) for name, value in six.iteritems(data)]}
        else:
            try:
                iter(data)
            except TypeError:
                six.raise_from(TypeError("uninterpretable type {}".format(type(data))), None)
            else:
                return {'type': "VertaList",
                        'name': "some_list_value",
                        'value': [ModelAPI._data_to_api(value, str(i)) for i, value in enumerate(data)]}

    @staticmethod
    def from_file(f):
        """
        Reads and returns a ``ModelAPI`` from a file.

        Parameters
        ----------
        f : str or file-like
            Model API JSON filesystem path or file.

        Returns
        -------
        :class:`ModelAPI`

        """
        if isinstance(f, six.string_types):
            f = open(f, 'r')

        model_api = ModelAPI(None, None)  # create a dummy instance
        model_api._buffer = six.StringIO(six.ensure_str(f.read()))
        return model_api

    def read(self, size=None):
        return self._buffer.read(size)

    def seek(self, offset, whence=0):
        self._buffer.seek(offset, whence)

    def tell(self):
        return self._buffer.tell()

    def to_dict(self):
        """
        Returns a copy of this model API as a dictionary.

        Returns
        -------
        dict

        """
        return json.loads(self.__str__())


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
