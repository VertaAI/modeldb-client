import itertools
import random

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

    def test_get_by_name(self, client):
        client.set_project()
        proj = client.set_project()
        client.set_project()

        assert proj.id == client.set_project(proj.name).id


class TestExperiment:
    def test_set_experiment_warning(self, client):
        client.set_project()
        expt = client.set_experiment()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_experiment(expt.name, **kwargs)

    def test_get_by_name(self, client):
        client.set_project()
        for _ in range(3):
            client.set_experiment()
        proj = client.set_project()
        client.set_experiment()
        expt = client.set_experiment()
        client.set_experiment()

        client.set_project(proj.name)
        assert expt.id == client.set_experiment(expt.name).id


class TestExperimentRun:
    def test_set_experiment_run_warning(self, client):
        client.set_project()
        client.set_experiment()
        expt_run = client.set_experiment_run()

        for kwargs in KWARGS_COMBOS:
            with pytest.warns(UserWarning):
                client.set_experiment_run(expt_run.name, **kwargs)

    def test_get_by_name(self, client):
        client.set_project()
        client.set_experiment()
        client.set_experiment_run()
        client.set_experiment_run()
        proj = client.set_project()
        expt = client.set_experiment()
        client.set_experiment_run()
        run = client.set_experiment_run()
        client.set_experiment_run()
        client.set_experiment()
        client.set_experiment_run()
        client.set_experiment_run()

        client.set_project(proj.name)
        client.set_experiment(expt.name)
        assert run.id == client.set_experiment_run(run.name).id


class TestExperimentRuns:
    def test_magic_getitem(self, client):
        client.set_project()
        expt = client.set_experiment()
        local_expt_run_ids = set()

        local_expt_run_ids.update(client.set_experiment_run().id for _ in range(3))
        backend_expt_run_ids = set(run.id for run in expt.expt_runs)
        assert local_expt_run_ids == backend_expt_run_ids

        local_expt_run_ids.update(client.set_experiment_run().id for _ in range(3))
        backend_expt_run_ids = set(run.id for run in expt.expt_runs)
        assert local_expt_run_ids == backend_expt_run_ids

    def test_magic_len(self, client):
        client.set_project()
        expt = client.set_experiment()
        expt_run_ids = [client.set_experiment_run().id for _ in range(3)]

        assert len(expt_run_ids) == len(expt.expt_runs)

    def test_magic_add(self, client):
        client.set_project()
        expt1 = client.set_experiment()
        local_expt1_run_ids = set(client.set_experiment_run().id for _ in range(3))
        expt2 = client.set_experiment()
        local_expt2_run_ids = set(client.set_experiment_run().id for _ in range(3))

        # simple concatenation
        assert local_expt1_run_ids | local_expt2_run_ids == set(run.id for run in expt1.expt_runs + expt2.expt_runs)

        # ignore duplicates
        assert local_expt1_run_ids == set(run.id for run in expt1.expt_runs + expt1.expt_runs)

    def test_find(self, client):
        client.set_project()
        expt = client.set_experiment()

        metric_vals = random.sample(range(36), 3)
        hyperparam_vals = random.sample(range(36), 3)
        for metric_val, hyperparam_val in zip(metric_vals, hyperparam_vals):
            run = client.set_experiment_run()
            run.log_metric('val', metric_val)
            run.log_hyperparameter('val', hyperparam_val)

        threshold = random.choice(metric_vals)
        local_filtered_run_ids = set(run.id for run in expt.expt_runs if run.get_metric('val') >= threshold)
        backend_filtered_run_ids = set(run.id for run in expt.expt_runs.find("metrics.val >= {}".format(threshold)))
        assert local_filtered_run_ids == backend_filtered_run_ids

        threshold = random.choice(hyperparam_vals)
        local_filtered_run_ids = set(run.id for run in expt.expt_runs if run.get_hyperparameter('val') >= threshold)
        backend_filtered_run_ids = set(run.id for run in expt.expt_runs.find("hyperparameters.val >= {}".format(threshold)))
        assert local_filtered_run_ids == backend_filtered_run_ids

    def test_sort(self, client):
        client.set_project()
        expt = client.set_experiment()

        vals = random.sample(range(36), 3)
        for val in vals:
            client.set_experiment_run().log_metric('val', val)

        sorted_run_ids = [run.id for run in sorted(expt.expt_runs, key=lambda run: run.get_metric('val'))]
        for expt_run_id, expt_run in zip(sorted_run_ids, expt.expt_runs.sort("metrics.val")):
            assert expt_run_id == expt_run.id

    def test_top_k(self, client):
        client.set_project()
        expt = client.set_experiment()

        metric_vals = random.sample(range(36), 3)
        hyperparam_vals = random.sample(range(36), 3)
        for metric_val, hyperparam_val in zip(metric_vals, hyperparam_vals):
            run = client.set_experiment_run()
            run.log_metric('val', metric_val)
            run.log_hyperparameter('val', hyperparam_val)

        k = random.randrange(3)
        top_run_ids = [run.id for run in sorted(expt.expt_runs,
                                                 key=lambda run: run.get_metric('val'), reverse=True)][:k]
        for expt_run_id, expt_run in zip(top_run_ids, expt.expt_runs.top_k("metrics.val", k)):
            assert expt_run_id == expt_run.id

        k = random.randrange(3)
        top_run_ids = [run.id for run in sorted(expt.expt_runs,
                                                 key=lambda run: run.get_metric('val'), reverse=True)][:k]
        for expt_run_id, expt_run in zip(top_run_ids, expt.expt_runs.top_k("metrics.val", k)):
            assert expt_run_id == expt_run.id

    def test_bottom_k(self, client):
        client.set_project()
        expt = client.set_experiment()

        metric_vals = random.sample(range(36), 3)
        hyperparam_vals = random.sample(range(36), 3)
        for metric_val, hyperparam_val in zip(metric_vals, hyperparam_vals):
            run = client.set_experiment_run()
            run.log_metric('val', metric_val)
            run.log_hyperparameter('val', hyperparam_val)

        k = random.randrange(3)
        bottom_run_ids = [run.id for run in sorted(expt.expt_runs,
                                                    key=lambda run: run.get_metric('val'))][:k]
        for expt_run_id, expt_run in zip(bottom_run_ids, expt.expt_runs.bottom_k("metrics.val", k)):
            assert expt_run_id == expt_run.id

        k = random.randrange(3)
        bottom_run_ids = [run.id for run in sorted(expt.expt_runs,
                                                    key=lambda run: run.get_metric('val'))][:k]
        for expt_run_id, expt_run in zip(bottom_run_ids, expt.expt_runs.bottom_k("metrics.val", k)):
            assert expt_run_id == expt_run.id
