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


class TestArtifacts:
    def test_datasets(self, run, output_path):
        # values represent literal artifacts
        datasets = {
            utils.gen_str(): utils.gen_str(),
            utils.gen_str(): utils.gen_str(),
        }

        # log
        for key, val in datasets.items():
            run.log_dataset(key, output_path.format(key), val)

        # try get nonexistent key
        with pytest.raises(KeyError):
            run.get_dataset(utils.gen_str())

        # get path
        for key in datasets.keys():
            assert run.get_dataset(key) == output_path.format(key)

        # load obj
        for key, val in datasets.items():
            assert run.get_dataset(key, load=True) == val

        # get all paths
        assert run.get_datasets() == dict(zip(datasets.keys(),
                                              [output_path.format(key) for key in datasets]))

        # load all objs
        assert run.get_datasets(load=True) == datasets

        # try load nonlocal obj
        new_key = utils.gen_str()
        datasets[new_key] = output_path.format(new_key)
        run.log_dataset(new_key, datasets[new_key])
        with pytest.raises(FileNotFoundError):
            run.get_dataset(new_key, load=True)
        with pytest.raises(FileNotFoundError):
            run.get_datasets(load=True, errors='raise')
        assert run.get_datasets(load=True, errors='ignore') == datasets

    def test_images(self, run, output_path):
        # values represent literal artifacts
        images = {
            utils.gen_str(): utils.gen_str(),
            utils.gen_str(): utils.gen_str(),
        }

        # log
        for key, val in images.items():
            run.log_image(key, output_path.format(key), val)

        # try get nonexistent key
        with pytest.raises(KeyError):
            run.get_image(utils.gen_str())

        # get path
        for key in images.keys():
            assert run.get_image(key) == output_path.format(key)

        # load obj
        for key, val in images.items():
            assert run.get_image(key, load=True) == val

        # get all paths
        assert run.get_images() == dict(zip(images.keys(),
                                            [output_path.format(key) for key in images]))

        # load all objs
        assert run.get_images(load=True) == images

        # try load nonlocal obj
        new_key = utils.gen_str()
        images[new_key] = output_path.format(new_key)
        run.log_image(new_key, images[new_key])
        with pytest.raises(FileNotFoundError):
            run.get_image(new_key, load=True)
        with pytest.raises(FileNotFoundError):
            run.get_images(load=True, errors='raise')
        assert run.get_images(load=True, errors='ignore') == images

    def test_models(self, run, output_path):
        # values represent literal artifacts
        models = {
            utils.gen_str(): utils.gen_str(),
            utils.gen_str(): utils.gen_str(),
        }

        # log
        for key, val in models.items():
            run.log_model(key, output_path.format(key), val)

        # try get nonexistent key
        with pytest.raises(KeyError):
            run.get_model(utils.gen_str())

        # get path
        for key in models.keys():
            assert run.get_model(key) == output_path.format(key)

        # load obj
        for key, val in models.items():
            assert run.get_model(key, load=True) == val

        # get all paths
        assert run.get_models() == dict(zip(models.keys(),
                                            [output_path.format(key) for key in models]))

        # load all objs
        assert run.get_models(load=True) == models

        # try load nonlocal obj
        new_key = utils.gen_str()
        models[new_key] = output_path.format(new_key)
        run.log_model(new_key, models[new_key])
        with pytest.raises(FileNotFoundError):
            run.get_model(new_key, load=True)
        with pytest.raises(FileNotFoundError):
            run.get_models(load=True, errors='raise')
        assert run.get_models(load=True, errors='ignore') == models


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
