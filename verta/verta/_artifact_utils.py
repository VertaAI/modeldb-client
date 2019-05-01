import six
import six.moves.cPickle as pickle

from verta import _utils

try:
    import joblib
except ImportError:  # joblib not installed
    pass

try:
    import cloudpickle
except ImportError:  # cloudpickle not installed
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
            joblib.dump(obj, bytestream)
        except NameError:  # joblib not installed
            pass
        except pickle.PicklingError:  # can't be handled by joblib
            pass
        else:
            bytestream.seek(0)
            return bytestream, "joblib"

        try:
            cloudpickle.dump(obj, bytestream)
        except NameError:  # cloudpickle not installed
            pass
        except pickle.PicklingError:  # can't be handled by cloudpickle
            pass
        else:
            bytestream.seek(0)
            return bytestream, "cloudpickle"

        pickle.dump(obj, bytestream)
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
