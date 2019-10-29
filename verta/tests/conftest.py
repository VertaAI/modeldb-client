from __future__ import division

import six

import os
import random
import shutil
import string

import verta
from verta import Client

import hypothesis
import pytest
import utils


RANDOM_SEED = 0
INPUT_LENGTH = 12  # length of iterable input fixture

DEFAULT_HOST = None
DEFAULT_PORT = None
DEFAULT_EMAIL = None
DEFAULT_DEV_KEY = None


# hypothesis on Jenkins is apparently too slow
hypothesis.settings.register_profile("default", suppress_health_check=[hypothesis.HealthCheck.too_slow])
hypothesis.settings.load_profile("default")


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


@pytest.fixture
def seed():
    return RANDOM_SEED


@pytest.fixture
def nones():
    return [None]*INPUT_LENGTH


@pytest.fixture
def bools(seed):
    random.seed(seed)
    return [bool(random.randint(0, 1)) for _ in range(INPUT_LENGTH)]


@pytest.fixture
def floats(seed):
    random.seed(seed)
    return [random.uniform(-3**2, 3**3) for _ in range(INPUT_LENGTH)]


@pytest.fixture
def ints(seed):
    random.seed(seed)
    return [random.randint(-3**4, 3**5) for _ in range(INPUT_LENGTH)]


@pytest.fixture
def strs(seed):
    """no duplicates"""
    random.seed(seed)
    gen_str = lambda: ''.join(random.choice(string.ascii_letters) for _ in range(INPUT_LENGTH))
    result = set()
    while len(result) < INPUT_LENGTH:
        single_str = gen_str()
        while single_str in result:
            single_str = gen_str()
        else:
            result.add(single_str)
    return list(result)


@pytest.fixture
def flat_lists(seed, nones, bools, floats, ints, strs):
    random.seed(seed)
    values = (nones, bools, floats, ints, strs)
    return [
        [
            values[random.choice(range(len(values)))][i]
            for i in range(INPUT_LENGTH)
        ]
        for _ in range(INPUT_LENGTH)
    ]


@pytest.fixture
def flat_dicts(seed, nones, bools, floats, ints, strs):
    random.seed(seed)
    values = (nones, bools, floats, ints, strs)
    return [
        {
            strs[i]: values[random.choice(range(len(values)))][i]
            for i in range(INPUT_LENGTH)
        }
        for _ in range(INPUT_LENGTH)
    ]


@pytest.fixture
def nested_lists(seed, nones, bools, floats, ints, strs):
    random.seed(seed)
    values = (nones, bools, floats, ints, strs)
    flat_values = [value for type_values in values for value in type_values]
    def gen_value(p=1):
        if random.random() < p:
            return [
                gen_value(p/2)
                for _ in range(random.choice(range(4)))
            ]
        else:
            return random.choice(flat_values)
    return [
        [
            gen_value()
            for _ in range(random.choice(range(3))+1)
        ]
        for _ in range(INPUT_LENGTH)
    ]


@pytest.fixture
def nested_dicts(seed, nones, bools, floats, ints, strs):
    random.seed(seed)
    values = (nones, bools, floats, ints, strs)
    flat_values = [value for type_values in values for value in type_values]
    def gen_value(p=1):
        if random.random() < p:
            return {
                key: gen_value(p/2)
                for key, _ in zip(strs, range(random.choice(range(4))))
            }
        else:
            return random.choice(flat_values)
    return [
        {
            key: gen_value()
            for key, _ in zip(strs, range(random.choice(range(3))+1))
        }
        for _ in range(INPUT_LENGTH)
    ]


@pytest.fixture
def scalar_values(nones, bools, floats, ints, strs):
    return [type_values[0]
            for type_values in (nones, bools, floats, ints, strs)]


@pytest.fixture
def collection_values(flat_lists, flat_dicts, nested_lists, nested_dicts):
    return [type_values[0]
            for type_values in (flat_lists, flat_dicts, nested_lists, nested_dicts)]


@pytest.fixture
def all_values(scalar_values, collection_values):
    return scalar_values + collection_values


@pytest.fixture(scope='session')
def output_path():
    dirpath = ".outputs"
    while len(dirpath) < 1024:
        try:  # avoid name collisions
            os.mkdir(dirpath)
        except OSError:
            dirpath += '_'
        else:
            yield os.path.join(dirpath, "{}")
            break
    else:
        raise RuntimeError("dirpath length exceeded 1024")
    shutil.rmtree(dirpath)


@pytest.fixture
def client(host, port, email, dev_key):
    client = Client(host, port, email, dev_key, debug=True)

    yield client

    if client.proj is not None:
        utils.delete_project(client.proj.id, client._conn)


@pytest.fixture
def experiment_run(client):
    client.set_project()
    client.set_experiment()
    return client.set_experiment_run()


@pytest.fixture
def created_datasets(client):
    """Container to track and clean up Datasets created during tests."""
    created_datasets = []

    yield created_datasets

    if created_datasets:
        utils.delete_datasets(list(set(dataset.id for dataset in created_datasets)), client._conn)
