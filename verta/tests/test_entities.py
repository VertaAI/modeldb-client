import itertools

import pytest
import utils


KWARGS = {
    'desc': [None, "A test."],
    'tags': [None, ['test']],
    'attrs': [None, {'is_test': True}],
}
KWARGS_COMBOS = [dict(zip(KWARGS.keys(), values))
                 for values
                 in itertools.product(*KWARGS.values())
                 if values.count(None) != len(values)]


class TestProject:
    def test_set_project_warning(self, client):
        proj = client.set_project()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_project(proj.name, **kwargs)


class TestExperiment:
    def test_set_experiment_warning(self, client):
        client.set_project()
        expt = client.set_experiment()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_experiment(expt.name, **kwargs)


class TestExperimentRuns:
    def test_magic_methods(self, client):
        client.set_project()
        expt1 = client.set_experiment()

        # __getitem__
        expt1_run_ids = [client.set_experiment_run()._id for _ in range(12)]
        for expt_run_id, expt_run in zip(expt1_run_ids, expt1.expt_runs):
            assert expt_run_id == expt_run._id

        # __len__
        assert len(expt1_run_ids) == len(expt1.expt_runs)

        # __add__
        expt2 = client.set_experiment()
        expt2_run_ids = [client.set_experiment_run()._id for _ in range(12)]
        for expt_run_id, expt_run in zip(expt1_run_ids + expt2_run_ids,
                                         expt1.expt_runs + expt2.expt_runs):
            assert expt_run_id == expt_run._id


class TestExperimentRun:
    def test_set_experiment_run_warning(self, client):
        client.set_project()
        client.set_experiment()
        expt_run = client.set_experiment_run()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_experiment_run(expt_run.name, **kwargs)
