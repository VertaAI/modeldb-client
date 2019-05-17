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


def reset_stream(stream):
    """
    Resets the cursor of a stream to the beginning.

    This is implemented with a try-except because not all file-like objects are guaranteed to have
    a ``seek()`` method, so we carry on if we cannot reset the pointer.

    Parameters
    ----------
    stream : file-like
        A stream that may or may not implement ``seek()``.

    """
    try:
        stream.seek(0)
    except AttributeError:
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
        reset_stream(obj)  # reset cursor to beginning in case user forgot
        contents = obj.read()  # read to cast into binary
        reset_stream(obj)  # reset cursor to beginning as a courtesy
        if not len(contents):
            raise ValueError("object contains no data")
        bytestring = six.ensure_binary(contents)
        bytestream = six.BytesIO(bytestring)
        bytestream.seek(0)
        return bytestream, None
    else:  # `obj` is not file-like
        bytestream = six.BytesIO()

        try:
            cloudpickle.dump(obj, bytestream)
        except pickle.PicklingError:  # can't be handled by cloudpickle
            pass
        else:
            bytestream.seek(0)
            return bytestream, "cloudpickle"

        try:
            joblib.dump(obj, bytestream)
        except (NameError,  # joblib not installed
                pickle.PicklingError):  # can't be handled by joblib
            pass
        else:
            bytestream.seek(0)
            return bytestream, "joblib"

        try:
            pickle.dump(obj, bytestream)
        except pickle.PicklingError:  # can't be handled by pickle
            six.raise_from(pickle.PicklingError("unable to serialize artifact"), None)
        else:
            bytestream.seek(0)
            return bytestream, "pickle"


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
    method : {"joblib", "cloudpickle", "pickle", "keras", None}
        Serialization method used to produce the bytestream.
    model_type : {"scikit", "xgboost", "tensorflow", "custom"}
        Framework with which the model was built.

    """
    if hasattr(model, 'read'):  # if `model` is file-like
        try:  # attempt to deserialize
            reset_stream(model)  # reset cursor to beginning in case user forgot
            model = deserialize_model(model.read())
        except pickle.UnpicklingError:  # unrecognized model
            bytestream = ensure_bytestream(model)  # pass along file-like
            method = None
            model_type = "custom"
        finally:
            reset_stream(model)  # reset cursor to beginning as a courtesy

    module_name = model.__class__.__module__ or "custom"
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
            method = "keras"
        else:
            bytestream, method = ensure_bytestream(model)
    elif package_name == 'xgboost':
        model_type = "xgboost"
        bytestream, method = ensure_bytestream(model)
    else:
        model_type = "custom"
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
    except (NameError,  # Tensorflow not installed
            OSError):  # not a Keras model
        bytestream.seek(0)
    try:
        return cloudpickle.load(bytestream)
    except pickle.UnpicklingError:  # not a pickled object
        bytestream.seek(0)
    return bytestream


def validate_requirements_txt(requirements):
    """
    Checks that all dependencies listed in `requirements` have an exact version pin.

    Parameters
    ----------
    requirements : file-like
        pip requirements file.

    Raises
    ------
    ValueError
        If a listed dependency does not have an exact version pin.

    """
    reset_stream(requirements)  # reset cursor to beginning in case user forgot
    contents = requirements.read()
    reset_stream(requirements)  # reset cursor to beginning as a courtesy

    for dependency in six.ensure_str(contents).split("\n"):
        if '==' not in dependency:
            raise ValueError("dependency '{}' must have an exact version pin".format(dependency))


def generate_model_api(data, serialization_method, model_type, num_outputs=1):
    """
    Generates the model API JSON from a model and data.

    `data` must begin with a header row, which is used to determine the API's field names. The first
    data row is then used to determine the API's field types.

    Parameters
    ----------
    data : str or file-like or pd.DataFrame
        Filepath to data CSV, CSV file handle, or DataFrame.
    serialization_method : {"joblib", "cloudpickle", "pickle", "keras"}
        Serialization method used to produce the model bytestream.
    model_type : {"scikit", "xgboost", "tensorflow", "custom"}
        Framework with which the model was built.
    num_outputs : int
        Number of output columns on the right-hand side of the CSV.

    Returns
    -------
    stringstream : file-like
        Model API JSON.

    """
    if serialization_method not in {"joblib", "cloudpickle", "pickle", "keras"}:
        raise ValueError("`serialization_method` must be one of {'joblib', 'cloudpickle', 'pickle', 'keras'}")
    if model_type not in {"scikit", "xgboost", "tensorflow", "custom"}:
        raise ValueError("`model_type` must be one of {'scikit', 'xgboost', 'tensorflow', 'custom'}")
    if num_outputs < 1:
        raise ValueError("`num_outputs` must be 1 or greater")

    # get first two rows from data
    if isinstance(data, six.string_types):  # if `data` is a filepath
        data = open(data, 'r')
    if hasattr(data, 'read'):  # if `data` is file-like
        reset_stream(data)  # reset cursor to beginning in case user forgot

        # read header and first data row
        reader = csv.reader(data)
        header = next(reader)
        row = next(reader)

        del reader
        reset_stream(data)  # reset cursor to beginning as a courtesy
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
        'input': input_fields[0] if len(input_fields) == 1 else {'type': "list", 'fields': input_fields},
        'output': output_fields[0] if len(output_fields) == 1 else {'type': "list", 'fields': output_fields},
    }
    stringstream = six.StringIO()
    json.dump(model_api, stringstream)
    stringstream.seek(0)
    return stringstream
