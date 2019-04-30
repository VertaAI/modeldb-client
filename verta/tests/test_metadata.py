import six

import pytest
import utils


if six.PY2: FileNotFoundError = IOError


class TestHyperparameters:
    hyperparameters = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    def test_single(self, experiment_run):
        for key, val in six.viewitems(self.hyperparameters):
            experiment_run.log_hyperparameter(key, val)

        with pytest.raises(KeyError):
            experiment_run.get_hyperparameter(utils.gen_str())

        for key, val in six.viewitems(self.hyperparameters):
            assert experiment_run.get_hyperparameter(key) == val

        assert experiment_run.get_hyperparameters() == self.hyperparameters

    def test_dict(self, experiment_run):
        with pytest.raises(ValueError):
            experiment_run.log_hyperparameters(self.hyperparameters, **self.hyperparameters)

        experiment_run.log_hyperparameters(self.hyperparameters)

        with pytest.raises(KeyError):
            experiment_run.get_hyperparameter(utils.gen_str())

        for key, val in six.viewitems(self.hyperparameters):
            assert experiment_run.get_hyperparameter(key) == val

        assert experiment_run.get_hyperparameters() == self.hyperparameters

    def test_unpack(self, experiment_run):
        experiment_run.log_hyperparameters(**self.hyperparameters)

        with pytest.raises(KeyError):
            experiment_run.get_hyperparameter(utils.gen_str())

        for key, val in six.viewitems(self.hyperparameters):
            assert experiment_run.get_hyperparameter(key) == val

        assert experiment_run.get_hyperparameters() == self.hyperparameters


class TestAttributes:
    attributes = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    def test_single(self, experiment_run):
        for key, val in six.viewitems(self.attributes):
            experiment_run.log_attribute(key, val)

        with pytest.raises(KeyError):
            experiment_run.get_attribute(utils.gen_str())

        for key, val in six.viewitems(self.attributes):
            assert experiment_run.get_attribute(key) == val

        assert experiment_run.get_attributes() == self.attributes


class TestMetrics:
    metrics = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    def test_single(self, experiment_run):
        for key, val in six.viewitems(self.metrics):
            experiment_run.log_metric(key, val)

        with pytest.raises(KeyError):
            experiment_run.get_metric(utils.gen_str())

        for key, val in six.viewitems(self.metrics):
            assert experiment_run.get_metric(key) == val

        assert experiment_run.get_metrics() == self.metrics


class TestObservations:
    observations = {
        utils.gen_str(): [utils.gen_str(), utils.gen_str()],
        utils.gen_str(): [utils.gen_int(), utils.gen_int()],
        utils.gen_str(): [utils.gen_float(), utils.gen_float()],
    }

    def test_single(self, experiment_run):
        for key, vals in six.viewitems(self.observations):
            for val in vals:
                experiment_run.log_observation(key, val)

        with pytest.raises(KeyError):
            experiment_run.get_observation(utils.gen_str())

        for key, val in six.viewitems(self.observations):
            assert experiment_run.get_observation(key) == val

        assert experiment_run.get_observations() == self.observations
