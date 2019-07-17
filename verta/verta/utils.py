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
    Init requires a list of potential x and y input

    Parameters
    ----------
    x : [{None, bool, int, float, str, dict, list}]
        An archetypal input for the model this API describes.
    y : [{None, bool, int, float, str, dict, list}]
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
    def _data_to_api(data, name=""):
        if hasattr(data, 'iloc'):  # if pandas
            if hasattr(data, 'columns'):  # if DataFrame
                if len(set(data.columns)) < len(data.columns):
                    raise ValueError("column names must all be unique")
                return {'type': "VertaList",
                        'name': name,
                        'value': [ModelAPI._data_to_api(data[name], str(name)) for name in data.columns]}
            elif hasattr(data, 'from_array'):  # if Series
                name = data.name
                data = data.iloc[0]
                if hasattr(data, 'item'):
                    data = data.item()
                # TODO: probably should use dtype instead of inferring the type?
                return ModelAPI._single_data_to_api(data, name)
        return ModelAPI._single_data_to_api(data[0], name)

    @staticmethod
    def _single_data_to_api(data, name=""):
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
                    'name': str(name)}
        elif isinstance(data, bool):  # did you know that `bool` is a subclass of `int`?
            return {'type': "VertaBool",
                    'name': str(name)}
        elif isinstance(data, numbers.Integral):
            return {'type': "VertaFloat", # float to be safe; the input might have been a one-off int
                    'name': str(name)}
        elif isinstance(data, numbers.Real):
            return {'type': "VertaFloat",
                    'name': str(name)}
        elif isinstance(data, six.string_types):
            return {'type': "VertaString",
                    'name': str(name)}
        elif isinstance(data, collections.Mapping):
            return {'type': "VertaJson",
                    'name': str(name),
                    'value': [ModelAPI._single_data_to_api(value, str(name)) for name, value in six.iteritems(data)]}
        else:
            try:
                iter(data)
            except TypeError:
                six.raise_from(TypeError("uninterpretable type {}".format(type(data))), None)
            else:
                return {'type': "VertaList",
                        'name': name,
                        'value': [ModelAPI._single_data_to_api(value, str(i)) for i, value in enumerate(data)]}

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

        model_api = ModelAPI([None], [None])  # create a dummy instance
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
