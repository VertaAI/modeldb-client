import six

import itertools
import os
import shutil

import requests

import pytest

import verta


KWARGS = {
    'desc': [None, "A test."],
    'tags': [None, ['test']],
    'attrs': [None, {'is_test': True}],
}
KWARGS_COMBOS = [dict(zip(KWARGS.keys(), values))
                 for values
                 in itertools.product(*KWARGS.values())
                 if values.count(None) != len(values)]


class TestClient:
    def test_verta_https(self):
        hosts = [
            "dev.verta.ai",
            "app.verta.ai",
            "sandbox.app.verta.ai",
        ]

        for host in hosts:
            # https by default
            conn = verta.Client(host)._conn
            assert conn.scheme == "https"
            assert conn.scheme == conn.auth['Grpc-Metadata-scheme']

            # http if provided
            conn = verta.Client("http://{}".format(host))._conn
            assert conn.scheme == "http"
            assert conn.scheme == conn.auth['Grpc-Metadata-scheme']

            # https if provided
            conn = verta.Client("https://{}".format(host))._conn
            assert conn.scheme == "https"
            assert conn.scheme == conn.auth['Grpc-Metadata-scheme']

    def test_else_http(self):
        # test hosts must not redirect http to https
        hosts = [
            "www.google.com",
        ]

        for host in hosts:
            # http by default
            try:
                verta.Client(host, max_retries=0)
            except requests.HTTPError as e:
                assert e.request.url.split(':', 1)[0] == "http"
            else:
                raise RuntimeError("faulty test; expected error")

            # http if provided
            try:
                verta.Client("http://{}".format(host), max_retries=0)
            except requests.HTTPError as e:
                assert e.request.url.split(':', 1)[0] == "http"
            else:
                raise RuntimeError("faulty test; expected error")

            # https if provided
            try:
                verta.Client("https://{}".format(host), max_retries=0)
            except requests.HTTPError as e:
                assert e.request.url.split(':', 1)[0] == "https"
            else:
                raise RuntimeError("faulty test; expected error")


class TestEntities:
    def test_cache(self, client, strs):
        entities = (
            client.set_project(),
            client.set_experiment(),
            client.set_experiment_run(),
        )

        for entity in entities:
            filename = strs[0]
            filepath = os.path.join(verta.client._CACHE_DIR, filename)
            contents = six.ensure_binary(strs[1])

            assert not os.path.isfile(filepath)
            assert not entity._get_cached(filename)

            try:
                assert entity._cache(filename, contents) == filepath

                assert os.path.isfile(filepath)
                assert entity._get_cached(filename)

                with open(filepath, 'rb') as f:
                    assert f.read() == contents
            finally:
                shutil.rmtree(verta.client._CACHE_DIR, ignore_errors=True)


class TestProject:
    def test_set_project_warning(self, client):
        """setting Project by name with desc, tags, and/or attrs raises warning"""
        proj = client.set_project()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_project(proj.name, **kwargs)

    def test_create(self, client):
        assert client.set_project()

        assert client.proj is not None

    def test_get_by_name(self, client):
        proj = client.set_project()

        client.set_project()  # in case get erroneously fetches latest

        assert proj.id == client.set_project(proj.name).id

    def test_get_by_id(self, client):
        proj = client.set_project()

        client.set_project()  # in case get erroneously fetches latest
        client.proj = None

        assert proj.id == client.set_project(id=proj.id).id

    def test_get_nonexistent_id(self, client):
        with pytest.raises(requests.HTTPError):  # 403 b/c Not Found == Unauth
            client.set_project(id="nonexistent_id")


class TestExperiment:
    def test_set_experiment_warning(self, client):
        """setting Experiment by name with desc, tags, and/or attrs raises warning"""
        client.set_project()
        expt = client.set_experiment()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_experiment(expt.name, **kwargs)

    def test_create(self, client):
        client.set_project()
        assert client.set_experiment()

        assert client.expt is not None

    def test_get_by_name(self, client):
        client.set_project()
        expt = client.set_experiment()

        client.set_experiment()  # in case get erroneously fetches latest

        assert expt.id == client.set_experiment(expt.name).id

    def test_get_by_id(self, client):
        proj = client.set_project()
        expt = client.set_experiment()

        client.set_experiment()  # in case get erroneously fetches latest
        client.proj = client.expt = None

        assert expt.id == client.set_experiment(id=expt.id).id
        assert proj.id == client.proj.id

    def test_get_nonexistent_id(self, client):
        with pytest.raises(ValueError):
            client.set_experiment(id="nonexistent_id")


class TestExperimentRun:
    def test_set_experiment_run_warning(self, client):
        """setting ExperimentRun by name with desc, tags, and/or attrs raises warning"""
        client.set_project()
        client.set_experiment()
        expt_run = client.set_experiment_run()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_experiment_run(expt_run.name, **kwargs)

    def test_create(self, client):
        client.set_project()
        client.set_experiment()

        assert client.set_experiment_run()

    def test_get_by_name(self, client):
        client.set_project()
        client.set_experiment()
        run = client.set_experiment_run()
        client.set_experiment_run()  # in case get erroneously fetches latest

        assert run.id == client.set_experiment_run(run.name).id

    def test_get_by_id(self, client):
        proj = client.set_project()
        expt = client.set_experiment()
        expt_run = client.set_experiment_run()

        client.set_experiment_run()  # in case get erroneously fetches latest
        client.proj = client.expt = None

        assert expt_run.id == client.set_experiment_run(id=expt_run.id).id
        assert proj.id == client.proj.id
        assert expt.id == client.expt.id

    def test_get_nonexistent_id(self, client):
        with pytest.raises(ValueError):
            client.set_experiment_run(id="nonexistent_id")


class TestExperimentRuns:
    def test_getitem(self, client):
        client.set_project()
        expt = client.set_experiment()

        # test for...in iteration
        local_run_ids = set(client.set_experiment_run().id for _ in range(3))
        assert local_run_ids == set(run.id for run in expt.expt_runs)

        # do it again
        local_run_ids.update(client.set_experiment_run().id for _ in range(3))
        assert local_run_ids == set(run.id for run in expt.expt_runs)

        # direct __getitem__
        assert expt.expt_runs[0].id in local_run_ids

    def test_len(self, client):
        client.set_project()
        expt = client.set_experiment()
        run_ids = [client.set_experiment_run().id for _ in range(3)]

        assert len(run_ids) == len(expt.expt_runs)

    def test_add(self, client):
        client.set_project()
        expt1 = client.set_experiment()
        local_expt1_run_ids = set(client.set_experiment_run().id for _ in range(3))
        expt2 = client.set_experiment()
        local_expt2_run_ids = set(client.set_experiment_run().id for _ in range(3))

        # simple concatenation
        assert local_expt1_run_ids | local_expt2_run_ids == set(run.id for run in expt1.expt_runs + expt2.expt_runs)

        # ignore duplicates
        assert local_expt1_run_ids == set(run.id for run in expt1.expt_runs + expt1.expt_runs)
