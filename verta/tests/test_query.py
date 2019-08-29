import numpy as np

import pytest


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
