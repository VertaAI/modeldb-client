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
        for key, val in self.hyperparameters.items():
            experiment_run.log_hyperparameter(key, val)

        with pytest.raises(KeyError):
            experiment_run.get_hyperparameter(utils.gen_str())

        for key, val in self.hyperparameters.items():
            assert experiment_run.get_hyperparameter(key) == val

        assert experiment_run.get_hyperparameters() == self.hyperparameters

    def test_dict(self, experiment_run):
        with pytest.raises(ValueError):
            experiment_run.log_hyperparameters(self.hyperparameters, **self.hyperparameters)

        experiment_run.log_hyperparameters(self.hyperparameters)

        with pytest.raises(KeyError):
            experiment_run.get_hyperparameter(utils.gen_str())

        for key, val in self.hyperparameters.items():
            assert experiment_run.get_hyperparameter(key) == val

        assert experiment_run.get_hyperparameters() == self.hyperparameters

    def test_unpack(self, experiment_run):
        experiment_run.log_hyperparameters(**self.hyperparameters)

        with pytest.raises(KeyError):
            experiment_run.get_hyperparameter(utils.gen_str())

        for key, val in self.hyperparameters.items():
            assert experiment_run.get_hyperparameter(key) == val

        assert experiment_run.get_hyperparameters() == self.hyperparameters


class TestArtifacts:
    def test_datasets(self, experiment_run, output_path):
        # values represent literal artifacts
        datasets = {
            utils.gen_str(): utils.gen_str(),
            utils.gen_str(): utils.gen_str(),
        }

        # log
        for key, val in datasets.items():
            experiment_run.log_dataset(key, output_path.format(key), val)

        # try get nonexistent key
        with pytest.raises(KeyError):
            experiment_run.get_dataset(utils.gen_str())

        # get path
        for key in datasets.keys():
            assert experiment_run.get_dataset(key) == output_path.format(key)

        # load obj
        for key, val in datasets.items():
            assert experiment_run.get_dataset(key, load=True) == val

        # get all paths
        assert experiment_run.get_datasets() == dict(zip(datasets.keys(),
                                              [output_path.format(key) for key in datasets]))

        # load all objs
        assert experiment_run.get_datasets(load=True) == datasets

        # try load nonlocal obj
        new_key = utils.gen_str()
        datasets[new_key] = output_path.format(new_key)
        experiment_run.log_dataset(new_key, datasets[new_key])
        with pytest.raises(FileNotFoundError):
            experiment_run.get_dataset(new_key, load=True)
        with pytest.raises(FileNotFoundError):
            experiment_run.get_datasets(load=True, errors='raise')
        assert experiment_run.get_datasets(load=True, errors='ignore') == datasets

    def test_images(self, experiment_run, output_path):
        # values represent literal artifacts
        images = {
            utils.gen_str(): utils.gen_str(),
            utils.gen_str(): utils.gen_str(),
        }

        # log
        for key, val in images.items():
            experiment_run.log_image(key, output_path.format(key), val)

        # try get nonexistent key
        with pytest.raises(KeyError):
            experiment_run.get_image(utils.gen_str())

        # get path
        for key in images.keys():
            assert experiment_run.get_image(key) == output_path.format(key)

        # load obj
        for key, val in images.items():
            assert experiment_run.get_image(key, load=True) == val

        # get all paths
        assert experiment_run.get_images() == dict(zip(images.keys(),
                                            [output_path.format(key) for key in images]))

        # load all objs
        assert experiment_run.get_images(load=True) == images

        # try load nonlocal obj
        new_key = utils.gen_str()
        images[new_key] = output_path.format(new_key)
        experiment_run.log_image(new_key, images[new_key])
        with pytest.raises(FileNotFoundError):
            experiment_run.get_image(new_key, load=True)
        with pytest.raises(FileNotFoundError):
            experiment_run.get_images(load=True, errors='raise')
        assert experiment_run.get_images(load=True, errors='ignore') == images

    def test_models(self, experiment_run, output_path):
        # values represent literal artifacts
        models = {
            utils.gen_str(): utils.gen_str(),
            utils.gen_str(): utils.gen_str(),
        }

        # log
        for key, val in models.items():
            experiment_run.log_model(key, output_path.format(key), val)

        # try get nonexistent key
        with pytest.raises(KeyError):
            experiment_run.get_model(utils.gen_str())

        # get path
        for key in models.keys():
            assert experiment_run.get_model(key) == output_path.format(key)

        # load obj
        for key, val in models.items():
            assert experiment_run.get_model(key, load=True) == val

        # get all paths
        assert experiment_run.get_models() == dict(zip(models.keys(),
                                            [output_path.format(key) for key in models]))

        # load all objs
        assert experiment_run.get_models(load=True) == models

        # try load nonlocal obj
        new_key = utils.gen_str()
        models[new_key] = output_path.format(new_key)
        experiment_run.log_model(new_key, models[new_key])
        with pytest.raises(FileNotFoundError):
            experiment_run.get_model(new_key, load=True)
        with pytest.raises(FileNotFoundError):
            experiment_run.get_models(load=True, errors='raise')
        assert experiment_run.get_models(load=True, errors='ignore') == models


def test_attributes(experiment_run):
    attributes = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    for key, val in attributes.items():
        experiment_run.log_attribute(key, val)

    with pytest.raises(KeyError):
        experiment_run.get_attribute(utils.gen_str())

    for key, val in attributes.items():
        assert experiment_run.get_attribute(key) == val

    assert experiment_run.get_attributes() == attributes


def test_metrics(experiment_run):
    metrics = {
        utils.gen_str(): utils.gen_str(),
        utils.gen_str(): utils.gen_int(),
        utils.gen_str(): utils.gen_float(),
    }

    for key, val in metrics.items():
        experiment_run.log_metric(key, val)

    with pytest.raises(KeyError):
        experiment_run.get_metric(utils.gen_str())

    for key, val in metrics.items():
        assert experiment_run.get_metric(key) == val

    assert experiment_run.get_metrics() == metrics


def test_observations(experiment_run):
    observations = {
        utils.gen_str(): [utils.gen_str(), utils.gen_str()],
        utils.gen_str(): [utils.gen_int(), utils.gen_int()],
        utils.gen_str(): [utils.gen_float(), utils.gen_float()],
    }

    for key, vals in observations.items():
        for val in vals:
            experiment_run.log_observation(key, val)

    with pytest.raises(KeyError):
        experiment_run.get_observation(utils.gen_str())

    for key, val in observations.items():
        assert experiment_run.get_observation(key) == val

    assert experiment_run.get_observations() == observations
