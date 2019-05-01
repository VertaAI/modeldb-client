import os
import shutil

from verta import Client

import pytest
import utils


DEFAULT_HOST = None
DEFAULT_PORT = None
DEFAULT_EMAIL = None
DEFAULT_DEV_KEY = None


@pytest.fixture(scope='session')
def host():
    return os.environ.get("VERTA_HOST", DEFAULT_HOST)


@pytest.fixture(scope='session')
def port():
    return os.environ.get("VERTA_PORT", DEFAULT_PORT)


@pytest.fixture(scope='session')
def email():
    return os.environ.get("VERTA_EMAIL", DEFAULT_EMAIL)


@pytest.fixture(scope='session')
def dev_key():
    return os.environ.get("VERTA_DEV_KEY", DEFAULT_DEV_KEY)


@pytest.fixture(scope='session')
def output_path():
    dirpath = ".outputs"
    while os.path.exists(dirpath):  # avoid name collisions
        dirpath += '_'
    yield os.path.join(dirpath, "{}")
    shutil.rmtree(dirpath)


@pytest.fixture
def client(host, port, email, dev_key):
    client = Client(host, port, email, dev_key)

    yield client

    if client.proj is not None:
        utils.delete_project(client.proj._id, client)


@pytest.fixture
def experiment_run(client):
    client.set_project()
    client.set_experiment()
    return client.set_experiment_run()
