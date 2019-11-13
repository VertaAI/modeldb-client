# -*- coding: utf-8 -*-

import six
import six.moves.cPickle as pickle

import csv
import importlib
import json
import os
import re
import tempfile
import warnings

import cloudpickle

from . import __about__
from . import _utils

try:
    import joblib
except ImportError:  # joblib not installed
    pass

try:
    from tensorflow import keras
except ImportError:  # TensorFlow not installed
    pass


def get_file_ext(file):
    """
    Obtain the filename extension of `file`.

    Parameters
    ----------
    file : str or file handle
        Filepath or on-disk file stream.

    Returns
    -------
    str
        Filename extension without the leading period.

    Raises
    ------
    TypeError
        If a filepath cannot be obtained from the argument.
    ValueError
        If the filepath lacks an extension.

    """
    if isinstance(file, six.string_types):
        filepath = file
    elif hasattr(file, 'read') and hasattr(file, 'name'):  # `open()` object
        filepath = file.name
    else:
        raise TypeError("unable to obtain filepath from object of type {}".format(type(file)))

    filename = os.path.basename(filepath).lstrip('.')
    try:
        _, extension = filename.split(os.extsep, 1)
    except ValueError:
        six.raise_from(ValueError("no extension found in \"{}\"".format(filepath)),
                       None)
    else:
        return extension


def ext_from_method(method):
    """
    Returns an appropriate file extension for a given model serialization method.

    Parameters
    ----------
    method : str
        The return value of `method` from ``serialize_model()``.

    Returns
    -------
    str or None
        Filename extension without the leading period.

    """
    if method == "keras":
        return 'hdf5'
    elif method in ("joblib", "cloudpickle", "pickle"):
        return 'pkl'
    elif method is None:
        return None
    else:
        raise ValueError("unrecognized method value: {}".format(method))


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
    model_type : {"torch", "sklearn", "xgboost", "tensorflow", "custom", "callable"}
        Framework with which the model was built.

    """
    if hasattr(model, 'read'):  # if `model` is file-like
        try:  # attempt to deserialize
            reset_stream(model)  # reset cursor to beginning in case user forgot
            model = deserialize_model(model.read())
        except pickle.UnpicklingError:  # unrecognized model
            bytestream, _ = ensure_bytestream(model)  # pass along file-like
            method = None
            model_type = "custom"
        finally:
            reset_stream(model)  # reset cursor to beginning as a courtesy

    for class_obj in model.__class__.__mro__:
        module_name = class_obj.__module__
        if not module_name:
            continue
        elif module_name.startswith("torch"):
            model_type = "torch"
            bytestream, method = ensure_bytestream(model)
            break
        elif module_name.startswith("sklearn"):
            model_type = "sklearn"
            bytestream, method = ensure_bytestream(model)
            break
        elif module_name.startswith("xgboost"):
            model_type = "xgboost"
            bytestream, method = ensure_bytestream(model)
            break
        elif module_name.startswith("tensorflow.python.keras"):
            model_type = "tensorflow"
            tempf = tempfile.NamedTemporaryFile()
            model.save(tempf.name)  # Keras provides this fn
            tempf.seek(0)
            bytestream = tempf
            method = "keras"
            break
    else:
        if hasattr(model, 'predict'):
            model_type = "custom"
            bytestream, method = ensure_bytestream(model)
        elif callable(model):
            model_type = "callable"
            bytestream, method = ensure_bytestream(model)
        else:
            raise TypeError("cannot determine the type for model argument")
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
    # try deserializing with Keras (HDF5)
    with tempfile.NamedTemporaryFile() as tempf:
        tempf.write(bytestring)
        tempf.seek(0)
        try:
            return keras.models.load_model(tempf.name)
        except (NameError,  # Tensorflow not installed
                IOError, OSError):  # not a Keras model
            pass

    # try deserializing with cloudpickle
    bytestream = six.BytesIO(bytestring)
    try:
        return cloudpickle.load(bytestream)
    except:  # not a pickled object
        bytestream.seek(0)

    return bytestream


def process_requirements(requirements):
    """
    Validates `requirements` against packages available in the current environment.

    Parameters
    ----------
    requirements : list of str
        PyPI package names.

    Raises
    ------
    ValueError
        If a listed dependency does not have an exact version pin.

    """
    PYPI_TO_IMPORT = {
        'scikit-learn': "sklearn",
        'tensorflow-gpu': "tensorflow",
    }
    REQ_SPEC_REGEX = re.compile(r"([a-zA-Z0-9._-]+)(.*)?")  # https://www.python.org/dev/peps/pep-0508/#names

    # clean up requirements
    requirements = [req.strip() for req in requirements]
    requirements = [req for req in requirements if not req.startswith('#')]  # comment line
    requirements = [req for req in requirements if req]  # empty line

    # validate package names
    for req in requirements:
        if not REQ_SPEC_REGEX.match(req):
            raise ValueError("'{}' does not appear to be a valid PyPI-installable package;"
                             " please check its spelling,"
                             " or report this as a bug if you believe it is in error".format(req))

    # warn for and strip version specifiers other than ==
    for i, req in enumerate(requirements):
        pkg, ver_spec = REQ_SPEC_REGEX.match(req).groups()
        if not ver_spec:
            continue
        elif '==' in ver_spec:
            continue
        else:
            msg = ("'{}' does not use '==';"
                   " for reproducibility in deployment,"
                   " it will be replaced with an exact version pin".format(req))
            warnings.warn(msg)
            requirements[i] = pkg

    # find version numbers from importable packages
    #     Because Python package management is complete anarchy, the Client can't determine
    #     whether the environment is using pip, pip3, or conda to check the installed version.
    for i, req in enumerate(requirements):
        error = ValueError("unable to determine a version number for requirement '{}';"
                           " please manually specify it as '{}==x.y.z'".format(req, req))
        if '==' not in req:
            mod_name = PYPI_TO_IMPORT.get(req, req)

            # obtain package version
            try:
                mod = importlib.import_module(mod_name)
            except ImportError:
                six.raise_from(error, None)
            try:
                ver = mod.__version__
            except AttributeError:
                six.raise_from(error, None)

            requirements[i] = mod_name + "==" + ver

    # add verta
    verta_req = "verta=={}".format(__about__.__version__)
    for req in requirements:
        if req.startswith("verta"):  # if present, check version
            our_ver = verta_req.split('==')[-1]
            their_ver = req.split('==')[-1]
            if our_ver != their_ver:  # versions conflict, so raise exception
                raise ValueError("Client is running with verta v{}, but the provided requirements specify v{};"
                                 " these must match".format(our_ver, their_ver))
            else:  # versions match, so proceed
                break
    else:  # if not present, add
        requirements.append(verta_req)

    # add cloudpickle
    cloudpickle_req = "cloudpickle=={}".format(cloudpickle.__version__)
    for req in requirements:
        if req.startswith("cloudpickle"):  # if present, check version
            our_ver = cloudpickle_req.split('==')[-1]
            their_ver = req.split('==')[-1]
            if our_ver != their_ver:  # versions conflict, so raise exception
                raise ValueError("Client is running with cloudpickle v{}, but the provided requirements specify v{};"
                                 " these must match".format(our_ver, their_ver))
            else:  # versions match, so proceed
                break
    else:  # if not present, add
        requirements.append(cloudpickle_req)

    return requirements
