import pytest
import utils


class TestHyperparameters:
    hyperparameters = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    def test_single(self, run):
        for key, val in self.hyperparameters.items():
            run.log_hyperparameter(key, val)

        with pytest.raises(KeyError):
            run.get_hyperparameter(utils.gen_str())

        for key, val in self.hyperparameters.items():
            assert run.get_hyperparameter(key) == val

        assert run.get_hyperparameters() == self.hyperparameters

    def test_dict(self, run):
        with pytest.raises(ValueError):
            run.log_hyperparameters(self.hyperparameters, **self.hyperparameters)

        run.log_hyperparameters(self.hyperparameters)

        with pytest.raises(KeyError):
            run.get_hyperparameter(utils.gen_str())

        for key, val in self.hyperparameters.items():
            assert run.get_hyperparameter(key) == val

        assert run.get_hyperparameters() == self.hyperparameters

    def test_unpack(self, run):
        run.log_hyperparameters(**self.hyperparameters)

        with pytest.raises(KeyError):
            run.get_hyperparameter(utils.gen_str())

        for key, val in self.hyperparameters.items():
            assert run.get_hyperparameter(key) == val

        assert run.get_hyperparameters() == self.hyperparameters


def test_attributes(run):
    attributes = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    for key, val in attributes.items():
        run.log_attribute(key, val)

    with pytest.raises(KeyError):
        run.get_attribute(utils.gen_str())

    for key, val in attributes.items():
        assert run.get_attribute(key) == val

    assert run.get_attributes() == attributes


def test_datasets(run):
    datasets = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_str(),
    }

    for key, val in datasets.items():
        run.log_dataset(key, val)

    with pytest.raises(KeyError):
        run.get_dataset(utils.gen_str())

    for key, val in datasets.items():
        assert run.get_dataset(key) == val

    assert run.get_datasets() == datasets


def test_images(run):
    images = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_str(),
    }

    for key, val in images.items():
        run.log_image(key, val)

    with pytest.raises(KeyError):
        run.get_image(utils.gen_str())

    for key, val in images.items():
        assert run.get_image(key) == val

    assert run.get_images() == images


def test_metrics(run):
    metrics = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    for key, val in metrics.items():
        run.log_metric(key, val)

    with pytest.raises(KeyError):
        run.get_metric(utils.gen_str())

    for key, val in metrics.items():
        assert run.get_metric(key) == val

    assert run.get_metrics() == metrics


def test_models(run):
    models = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_str(),
    }

    for key, val in models.items():
        run.log_model(key, val)

    with pytest.raises(KeyError):
        run.get_model(utils.gen_str())

    for key, val in models.items():
        assert run.get_model(key) == val

    assert run.get_models() == models


def test_observations(run):
    observations = {
        utils.gen_str(): [utils.gen_str(), utils.gen_str()],
        utils.gen_str(): [utils.gen_int(), utils.gen_int()],
        utils.gen_str(): [utils.gen_float(), utils.gen_float()],
    }

    for key, vals in observations.items():
        for val in vals:
            run.log_observation(key, val)

    with pytest.raises(KeyError):
        run.get_observation(utils.gen_str())

    for key, val in observations.items():
        assert run.get_observation(key) == val

    assert run.get_observations() == observations
