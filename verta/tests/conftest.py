import os
import shutil

from google.cloud import bigquery

from verta import Client

import pytest
import utils


DEFAULT_HOST = None
DEFAULT_PORT = None
DEFAULT_EMAIL = None
DEFAULT_DEV_KEY = None

DEFAULT_S3_TEST_BUCKET = None
DEFAULT_S3_TEST_OBJECT = None
DEFAULT_GOOGLE_APPLICATION_CREDENTIALS = None


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


@pytest.fixture(scope='session')
def path_dataset_dir():
    dirpath = ".path-dataset"
    while os.path.exists(dirpath):  # avoid name collisions
        dirpath += '_'
    yield os.path.join(dirpath, "{}")
    shutil.rmtree(dirpath)


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
