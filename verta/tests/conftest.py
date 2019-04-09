import os
import shutil

import pytest
import utils

from verta import ModelDBClient
from verta.modeldbclient import Project, Experiment, ExperimentRun


HOST_ENV_VAR = "MODELDB_HOST"
PORT_ENV_VAR = "MODELDB_PORT"
EMAIL_ENV_VAR = "MODELDB_EMAIL"
DEV_KEY_ENV_VAR = "MODELDB_DEV_KEY"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = "8080"
DEFAULT_EMAIL = None
DEFAULT_DEV_KEY = None


@pytest.fixture(scope='session')
def host():
    return os.environ.get(HOST_ENV_VAR, DEFAULT_HOST)


@pytest.fixture(scope='session')
def port():
    return os.environ.get(PORT_ENV_VAR, DEFAULT_PORT)


@pytest.fixture(scope='session')
def email():
    return os.environ.get(EMAIL_ENV_VAR, DEFAULT_EMAIL)


@pytest.fixture(scope='session')
def dev_key():
    return os.environ.get(DEV_KEY_ENV_VAR, DEFAULT_DEV_KEY)


@pytest.fixture(scope='session')
def output_path():
    dirpath = ".outputs"
    while os.path.exists(dirpath):  # avoid name collisions
        dirpath += '_'
    yield os.path.join(dirpath, "{}")
    shutil.rmtree(dirpath)


@pytest.fixture
def client(host, port, email, dev_key):
    client = ModelDBClient(host, port, email, dev_key)
    yield client
    if client.proj is not None:
        utils.delete_project(client.proj._id, client)


@pytest.fixture
def project(client):
    proj = Project._create(client._auth, client._socket,
                           Project._generate_default_name())
    yield proj
    utils.delete_project(proj._id, client)


@pytest.fixture
def experiment(project, client):
    expt = Experiment._create(client._auth, client._socket,
                              project._id,
                              Experiment._generate_default_name())
    yield expt
    utils.delete_experiment(expt._id, client)


@pytest.fixture
def experiment_run(project, experiment, client):
    expt_run = ExperimentRun._create(client._auth, client._socket,
                                     project._id, experiment._id,
                                     ExperimentRun._generate_default_name())
    yield expt_run
    utils.delete_experiment_run(expt_run._id, client)
