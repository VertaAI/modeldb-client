import six

import pytest
import utils


class TestTags:
    tags = [utils.gen_str() for _ in range(3)]

    def test_single(self, experiment_run):
        for tag in self.tags:
            experiment_run.log_tag(tag)

        assert set(experiment_run.get_tags()) == set(self.tags)

    def test_multiple(self, experiment_run):
        experiment_run.log_tags(self.tags)

        assert set(experiment_run.get_tags()) == set(self.tags)

    def test_duplicates(self, experiment_run):
        experiment_run.log_tags(self.tags)
        for tag in self.tags:
            experiment_run.log_tag(tag)

        assert set(experiment_run.get_tags()) == set(self.tags)


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

    def test_batch(self, experiment_run):
        experiment_run.log_hyperparameters(self.hyperparameters)

        with pytest.raises(KeyError):
            experiment_run.get_hyperparameter(utils.gen_str())

        for key, val in six.viewitems(self.hyperparameters):
            assert experiment_run.get_hyperparameter(key) == val

        assert experiment_run.get_hyperparameters() == self.hyperparameters

    def test_conflict(self, experiment_run):
        for key, val in six.viewitems(self.hyperparameters):
            experiment_run.log_hyperparameter(key, val)
            with pytest.raises(ValueError):
                experiment_run.log_hyperparameter(key, val)

        for key, val in reversed(list(six.viewitems(self.hyperparameters))):
            with pytest.raises(ValueError):
                experiment_run.log_hyperparameter(key, val)

    def test_atomic(self, experiment_run):
        """Test if batch completely fails even if only a single key conflicts."""
        experiment_run.log_hyperparameters(self.hyperparameters)

        for key, val in six.viewitems(self.hyperparameters):
            with pytest.raises(ValueError):
                experiment_run.log_hyperparameters({
                    key: val,
                    utils.gen_str(): utils.gen_str(),
                })

        assert experiment_run.get_hyperparameters() == self.hyperparameters

    def test_log_collection(self, experiment_run):
        with pytest.raises(TypeError):  # single fn, list
            experiment_run.log_hyperparameter(utils.gen_str(), utils.gen_list())

        with pytest.raises(TypeError):  # batch fn, list
            experiment_run.log_hyperparameters({utils.gen_str(): utils.gen_list()})

        with pytest.raises(TypeError):  # single fn, dict
            experiment_run.log_hyperparameter(utils.gen_str(), utils.gen_dict())

        with pytest.raises(TypeError):  # batch fn, dict
            experiment_run.log_hyperparameters({utils.gen_str(): utils.gen_dict()})



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

    def test_batch(self, experiment_run):
        experiment_run.log_attributes(self.attributes)

        with pytest.raises(KeyError):
            experiment_run.get_attribute(utils.gen_str())

        for key, val in six.viewitems(self.attributes):
            assert experiment_run.get_attribute(key) == val

        assert experiment_run.get_attributes() == self.attributes

    def test_conflict(self, experiment_run):
        for key, val in six.viewitems(self.attributes):
            experiment_run.log_attribute(key, val)
            with pytest.raises(ValueError):
                experiment_run.log_attribute(key, val)

        for key, val in reversed(list(six.viewitems(self.attributes))):
            with pytest.raises(ValueError):
                experiment_run.log_attribute(key, val)

    def test_atomic(self, experiment_run):
        """Test if batch completely fails even if only a single key conflicts."""
        experiment_run.log_attributes(self.attributes)

        for key, val in six.viewitems(self.attributes):
            with pytest.raises(ValueError):
                experiment_run.log_attributes({
                    key: val,
                    utils.gen_str(): utils.gen_str(),
                })

        assert experiment_run.get_attributes() == self.attributes

    def test_log_collection(self, experiment_run):
        # single fn, list
        key, value = utils.gen_str(), utils.gen_list()
        experiment_run.log_attribute(key, value)
        assert experiment_run.get_attribute(key) == value

        # batch fn, list
        key, value = utils.gen_str(), utils.gen_list()
        experiment_run.log_attributes({key: value})
        assert experiment_run.get_attribute(key) == value

        # single fn, dict
        key, value = utils.gen_str(), utils.gen_dict()
        experiment_run.log_attribute(key, value)
        assert experiment_run.get_attribute(key) == value

        # batch fn, dict
        key, value = utils.gen_str(), utils.gen_dict()
        experiment_run.log_attributes({key: value})
        assert experiment_run.get_attribute(key) == value


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

    def test_batch(self, experiment_run):
        experiment_run.log_metrics(self.metrics)

        with pytest.raises(KeyError):
            experiment_run.get_metric(utils.gen_str())

        for key, val in six.viewitems(self.metrics):
            assert experiment_run.get_metric(key) == val

        assert experiment_run.get_metrics() == self.metrics

    def test_conflict(self, experiment_run):
        for key, val in six.viewitems(self.metrics):
            experiment_run.log_metric(key, val)
            with pytest.raises(ValueError):
                experiment_run.log_metric(key, val)

        for key, val in reversed(list(six.viewitems(self.metrics))):
            with pytest.raises(ValueError):
                experiment_run.log_metric(key, val)

    def test_atomic(self, experiment_run):
        """Test if batch completely fails even if only a single key conflicts."""
        experiment_run.log_metrics(self.metrics)

        for key, val in six.viewitems(self.metrics):
            with pytest.raises(ValueError):
                experiment_run.log_metrics({
                    key: val,
                    utils.gen_str(): utils.gen_str(),
                })

        assert experiment_run.get_metrics() == self.metrics

    def test_log_collection(self, experiment_run):
        with pytest.raises(TypeError):  # single fn, list
            experiment_run.log_metric(utils.gen_str(), utils.gen_list())

        with pytest.raises(TypeError):  # batch fn, list
            experiment_run.log_metrics({utils.gen_str(): utils.gen_list()})

        with pytest.raises(TypeError):  # single fn, dict
            experiment_run.log_metric(utils.gen_str(), utils.gen_dict())

        with pytest.raises(TypeError):  # batch fn, dict
            experiment_run.log_metrics({utils.gen_str(): utils.gen_dict()})


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
            assert [obs_val for obs_val, _ in experiment_run.get_observation(key)] == val

        assert {key: [obs_val for obs_val, _ in obs_seq]
                for key, obs_seq in experiment_run.get_observations().items()} == self.observations

    def test_log_collection(self, experiment_run):
        with pytest.raises(TypeError):  # single fn, list
            experiment_run.log_observation(utils.gen_str(), utils.gen_list())

        with pytest.raises(TypeError):  # single fn, dict
            experiment_run.log_observation(utils.gen_str(), utils.gen_dict())
