import six

from multiprocessing import Pool

import pytest
import utils


class TestLoad:
    @staticmethod
    def run_fake_experiment(client):
        run = client.set_experiment_run()

        run.log_attribute("is_test", True)
        run.get_attribute("is_test")

        run.log_hyperparameters({
            'C': utils.gen_float(),
            'solver': utils.gen_str(),
            'max_iter': utils.gen_int(),
        })
        run.get_hyperparameter("C")
        run.get_hyperparameter("solver")
        run.get_hyperparameter("max_iter")

        run.log_observation("rand_val", utils.gen_float())
        run.log_observation("rand_val", utils.gen_float())
        run.log_observation("rand_val", utils.gen_float())
        run.get_observation("rand_val")

        run.log_metric("val_acc", utils.gen_float())
        run.get_metric("val_acc")

        run.log_artifact("self", run)
        run.get_artifact("self")

    @pytest.mark.skip(reason="there is an issue serializing the Client for Pool")
    def test_load(self, client):
        client.set_project()
        client.set_experiment()
        with Pool(36) as pool:
            pool.map(self.run_fake_experiment, [client]*180)
