import os
import shutil
import string

from google.cloud import bigquery
import numpy as np

from verta import Client

import pytest
import utils


RANDOM_SEED = 0
INPUT_LENGTH = 12  # length of iterable input fixture

DEFAULT_HOST = None
DEFAULT_PORT = None
DEFAULT_EMAIL = None
DEFAULT_DEV_KEY = None

DEFAULT_S3_TEST_BUCKET = "bucket"
DEFAULT_S3_TEST_OBJECT = "object"
DEFAULT_GOOGLE_APPLICATION_CREDENTIALS = "credentials.json"


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
def nones():
    return [None]*INPUT_LENGTH


@pytest.fixture
def bools():
    np.random.seed(RANDOM_SEED)
    return np.random.randint(0, 2, INPUT_LENGTH).astype(bool).tolist()


@pytest.fixture
def floats():
    np.random.seed(RANDOM_SEED)
    return np.linspace(-3**2, 3**3, num=INPUT_LENGTH).tolist()


@pytest.fixture
def ints():
    np.random.seed(RANDOM_SEED)
    return np.linspace(-3**4, 3**5, num=INPUT_LENGTH).astype(int).tolist()


@pytest.fixture
def strs():
    """no duplicates"""
    np.random.seed(RANDOM_SEED)
    gen_str = lambda: ''.join(np.random.choice(list(string.ascii_letters), size=INPUT_LENGTH))
    result = set()
    while len(result) < INPUT_LENGTH:
        single_str = gen_str()
        while single_str in result:
            single_str = gen_str()
        else:
            result.add(single_str)
    return list(result)


@pytest.fixture
def flat_lists(nones, bools, floats, ints, strs):
    np.random.seed(RANDOM_SEED)
    values = (nones, bools, floats, ints, strs)
    return [
        [
            values[np.random.choice(len(values))][i]
            for i in range(INPUT_LENGTH)
        ]
        for _ in range(INPUT_LENGTH)
    ]


@pytest.fixture
def flat_dicts(nones, bools, floats, ints, strs):
    np.random.seed(RANDOM_SEED)
    values = (nones, bools, floats, ints, strs)
    return [
        {
            strs[i]: values[np.random.choice(len(values))][i]
            for i in range(INPUT_LENGTH)
        }
        for _ in range(INPUT_LENGTH)
    ]


@pytest.fixture
def nested_lists(nones, bools, floats, ints, strs):
    np.random.seed(RANDOM_SEED)
    values = (nones, bools, floats, ints, strs)
    flat_values = [value for type_values in values for value in type_values]
    def gen_value(p=1):
        if np.random.random() < p:
            return [
                gen_value(p/2)
                for _ in range(np.random.choice(4))
            ]
        else:
            return np.random.choice(flat_values)
    return [
        [
            gen_value()
            for _ in range(np.random.choice(3)+1)
        ]
        for _ in range(INPUT_LENGTH)
    ]


@pytest.fixture
def nested_dicts(nones, bools, floats, ints, strs):
    np.random.seed(RANDOM_SEED)
    values = (nones, bools, floats, ints, strs)
    flat_values = [value for type_values in values for value in type_values]
    def gen_value(p=1):
        if np.random.random() < p:
            return {
                key: gen_value(p/2)
                for key, _ in zip(strs, range(np.random.choice(4)))
            }
        else:
            return np.random.choice(flat_values)
    return [
        {
            key: gen_value()
            for key, _ in zip(strs, range(np.random.choice(3)+1))
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
    client = Client(host, port, email, dev_key)

    yield client

    if client.proj is not None:
        utils.delete_project(client.proj.id, client._conn)


@pytest.fixture
def experiment_run(client):
    client.set_project()
    client.set_experiment()
    return client.set_experiment_run()


@pytest.fixture(scope='session')
def s3_bucket():
    return os.environ.get("S3_TEST_BUCKET", DEFAULT_S3_TEST_BUCKET)


@pytest.fixture(scope='session')
def s3_object():
    return os.environ.get("S3_TEST_OBJECT", DEFAULT_S3_TEST_OBJECT)


@pytest.fixture(scope="session")
def big_query_job():
    # needs to be set
    #_ = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_GOOGLE_APPLICATION_CREDENTIALS)
    query = (
        """SELECT
        id,
        `by`,
        score,
        time,
        time_ts,
        title,
        url,
        text,
        deleted,
        dead,
        descendants,
        author
        FROM
        `bigquery-public-data.hacker_news.stories`
        LIMIT
        1000"""
    )
    query_job = bigquery.Client().query(
        query,
        # Location must match that of the dataset(s) referenced in the query.
        location="US",
    )
    job_id = query_job.job_id
    return (job_id, "US", query)
