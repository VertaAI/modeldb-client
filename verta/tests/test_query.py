import six

import numpy as np

import pytest

import verta


OPERATORS = six.viewkeys(verta.client.ExperimentRuns._OP_MAP)


class TestFind:
    def test_reject_unsupported_keys(self, client, floats):
        keys = (
            'name', 'description',
            'code_version', 'code_version_snapshot',
            'parent_id',
            'artifacts', 'datasets',
            'observations', 'features',
            'job_id', 'owner',
        )
        proj = client.set_project()
        expt = client.set_experiment()

        for _ in range(3):
            client.set_experiment_run()

        # known unsupported keys
        for expt_runs in (proj.expt_runs, expt.expt_runs):
            for key in keys:
                for op, val in zip(OPERATORS, floats):
                    with pytest.raises(ValueError):
                        expt_runs.find("{} {} {}".format(key, op, val))

    def test_reject_random_keys(self, client, strs, floats):
        proj = client.set_project()
        expt = client.set_experiment()

        for _ in range(3):
            client.set_experiment_run()

        for expt_runs in (proj.expt_runs, expt.expt_runs):
            for key in strs:
                for op, val in zip(OPERATORS, floats):
                    with pytest.raises(ValueError):
                        expt_runs.find("{} {} {}".format(key, op, val))

    def test_id(self, client):
        proj = client.set_project()
        client.set_experiment()
        runs = [client.set_experiment_run() for _ in range(3)]

        for run_id in (run.id for run in runs):
            result = proj.expt_runs.find("id == '{}'".format(run_id))
            assert len(result) == 1
            assert result[0].id == run_id

    def test_project_id(self, client):
        proj = client.set_project()
        client.set_experiment()
        runs = [client.set_experiment_run() for _ in range(3)]
        client.set_experiment()
        runs.extend([client.set_experiment_run() for _ in range(3)])

        result = proj.expt_runs.find("project_id == '{}'".format(proj.id))
        assert set(run.id for run in result) == set(run.id for run in runs)

    def test_experiment_id(self, client):
        proj = client.set_project()
        client.set_experiment()
        [client.set_experiment_run() for _ in range(3)]
        expt = client.set_experiment()
        runs = [client.set_experiment_run() for _ in range(3)]

        result = proj.expt_runs.find("experiment_id == '{}'".format(expt.id))
        assert set(run.id for run in result) == set(run.id for run in runs)

    @pytest.mark.skip(reason="not implemented")
    def test_date_created(self, client):
        key = "date_created"

    @pytest.mark.skip(reason="not implemented")
    def test_date_updated(self, client):
        key = "date_updated"

    @pytest.mark.skip(reason="not implemented")
    def test_start_time(self, client):
        key = "start_time"

    @pytest.mark.skip(reason="not implemented")
    def test_end_time(self, client):
        key = "end_time"

    @pytest.mark.skip(reason="not implemented")
    def test_tags(self, client):
        key = "tags"

    @pytest.mark.skip(reason="not implemented")
    def test_attributes(self, client):
        key = "attributes"

    @pytest.mark.skip(reason="not implemented")
    def test_hyperparameters(self, client):
        key = "hyperparameters"

    @pytest.mark.skip(reason="not implemented")
    def test_metrics(self, client, strs, bools, floats):
        key = "metrics"
        proj = client.set_project()
        expt = client.set_experiment()


@pytest.mark.skip(reason="obsolete")
class TestQuery:
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
