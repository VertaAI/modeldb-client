import six
import six.moves.cPickle as pickle

import csv
import json
import sys

import cloudpickle

from verta import _utils

try:
    import joblib
except ImportError:  # joblib not installed
    pass

try:
    from tensorflow import keras
except ImportError:  # TensorFlow not installed
    pass


def ensure_bytestream(obj):
    """
    Converts an object into a bytestream.

    If `obj` is file-like, its contents will be read into memory and then wrapped in a bytestream.
    This has a performance cost, but checking beforehand whether an arbitrary file-like object
    returns bytes rather than encoded characters is an implementation nightmare.

    If `obj` is not file-like, it will be serialized and then wrapped in a bytestream.

    Parameters
    ----------
    obj : file-like or object
        Object to convert into a bytestream.

    Returns
    -------
    bytestream : file-like
        Buffered bytestream of the serialized artifacts.
    method : {"joblib", "cloudpickle", "pickle", None}
        Serialization method used to produce the bytestream.

    Raises
    ------
    pickle.PicklingError
        If `obj` cannot be serialized.
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
        bytestream = six.BytesIO(bytestring)
        bytestream.seek(0)
        return bytestream, None
    else:  # `obj` is not file-like
        bytestream = six.BytesIO()

        try:
            pickle.dump(obj, bytestream)
        except pickle.PicklingError:  # can't be handled by pickle
            pass
        else:
            bytestream.seek(0)
            return bytestream, "pickle"

        try:
            joblib.dump(obj, bytestream)
        except NameError:  # joblib not installed
            pass
        except pickle.PicklingError:  # can't be handled by joblib
            pass
        else:
            bytestream.seek(0)
            return bytestream, "joblib"

        cloudpickle.dump(obj, bytestream)
        bytestream.seek(0)
        return bytestream, "cloudpickle"


def serialize_model(model):
    """
    Serializes a model into a bytestream, attempting various methods.

    Parameters
    ----------
    model : object or file-like
        Model to convert into a bytestream.

    Returns
    -------
    bytestream : file-like
        Buffered bytestream of the serialized model.
    method : {"joblib", "cloudpickle", "pickle", None}
        Serialization method used to produce the bytestream.
    model_type : {"scikit", "xgboost", "tensorflow", "unknown"}
        Framework with which the model was built.

    """
    if hasattr(model, 'read'):  # if `model` is file-like
        try:  # attempt to deserialize
            try:  # reset cursor to beginning in case user forgot
                model.seek(0)
            except AttributeError:
                pass
            model = deserialize_model(model.read())
        except pickle.UnpicklingError:  # unrecognized model
            bytestream = ensure_bytestream(model)  # pass along file-like
            method = None
            model_type = "unknown"
        finally:
            try:  # reset cursor to beginning as a courtesy
                model.seek(0)
            except AttributeError:
                pass

    module_name = model.__class__.__module__ or "unknown"
    package_name = module_name.split('.')[0]

    if package_name == 'sklearn':
        model_type = "scikit"
        bytestream, method = ensure_bytestream(model)
    elif package_name == 'tensorflow':
        model_type = "tensorflow"
        if "keras" in module_name.split('.'):  # Keras provides a model.save() method
            bytestream = six.BytesIO()
            model.save(bytestream)
            bytestream.seek(0)
            method = None
        else:
            bytestream, method = ensure_bytestream(model)
    elif package_name == 'xgboost':
        model_type = "xgboost"
        bytestream, method = ensure_bytestream(model)
    else:
        model_type = "unknown"
        bytestream, method = ensure_bytestream(model)

    return bytestream, method, model_type


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


def generate_model_api(data, serialization_method, model_type, num_outputs=1):
    """
    Generates the model API JSON from a model and data.

    `data` must begin with a header row, which is used to determine the API's field names. The first
    data row is then used to determine the API's field types.

    Parameters
    ----------
    data : str or file-like or pd.DataFrame
        Filepath to data CSV, CSV file handle, or DataFrame.
    serialization_method : {"joblib", "cloudpickle", "pickle", None}
        Serialization method used to produce the model bytestream.
    model_type : {"scikit", "xgboost", "tensorflow", "unknown"}
        Framework with which the model was built.
    num_outputs : int
        Number of output columns on the right-hand side of the CSV.

    Returns
    -------
    stringstream : file-like
        Model API JSON.

    """
    if serialization_method not in {"joblib", "cloudpickle", "pickle", None}:
        raise ValueError("`serialization_method` must be one of {'joblib', 'cloudpickle', 'pickle', None}")
    if model_type not in {"scikit", "xgboost", "tensorflow", "unknown"}:
        raise ValueError("`model_type` must be one of {'scikit', 'xgboost', 'tensorflow', 'unknown'}")
    if num_outputs < 1:
        raise ValueError("`num_outputs` must be 1 or greater")

    # get first two rows from data
    if isinstance(data, six.string_types):  # if `data` is a filepath
        data = open(data, 'r')
    if hasattr(data, 'read'):  # if `data` is file-like
        try:  # reset cursor to beginning in case user forgot
            data.seek(0)
        except AttributeError:
            pass

        # read header and first data row
        reader = csv.reader(data)
        header = next(reader)
        row = next(reader)

        del reader
        try:  # reset cursor to beginning as a courtesy
            data.seek(0)
        except AttributeError:
            pass
    elif hasattr(data, 'iloc'):  # if `data` is a DataFrame
        header = data.columns
        row = data.iloc[0]
    else:
        raise ValueError("`data` must be a filepath, a file object, or a DataFrame")

    # parse data
    fields = []
    for col_name, val in zip(header, row):
        try:
            float(val)
        except ValueError:
            val_type = "str"
        else:
            val_type = "float"

        fields.append({'name': col_name, 'type': val_type})

    input_fields, output_fields = fields[:-num_outputs], fields[-num_outputs:]
    if not len(input_fields):
        raise ValueError("`num_outputs` must be less than the total number of columns")

    model_api = {
        'model_type': model_type,
        'python_version': sys.version_info[0],
        'deserialization': serialization_method,
        'input': {'type': "list", 'fields': input_fields},
        'output': {'type': "list", 'fields': output_fields},
    }
    if serialization_method is None:
        del model_api['deserialization']
    stringstream = six.StringIO()
    json.dump(model_api, stringstream)
    stringstream.seek(0)
    return stringstream
