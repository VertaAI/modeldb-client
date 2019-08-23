import six

import sys

if sys.platform == "darwin":  # https://stackoverflow.com/q/21784641
    import matplotlib
    matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np
import PIL
import PIL.ImageDraw
import sklearn.linear_model

import pytest
import utils


class TestArtifacts:
    def test_path(self, experiment_run):
        key = utils.gen_str()
        path = utils.gen_str()

        experiment_run.log_artifact_path(key, path)
        assert experiment_run.get_artifact(key) == path

    def test_store(self, experiment_run):
        key = utils.gen_str()
        artifact = {utils.gen_str(): utils.gen_str() for _ in range(6)}

        experiment_run.log_artifact(key, artifact)
        assert experiment_run.get_artifact(key) == artifact

    def test_empty(self, experiment_run):
        artifacts = {
            utils.gen_str(): six.BytesIO(),
        }

        for key, artifact in six.viewitems(artifacts):
            with pytest.raises(ValueError):
                experiment_run.log_artifact(key, artifact)

    def test_get(self, experiment_run):
        artifacts = {
            utils.gen_str(): {utils.gen_str(): utils.gen_str() for _ in range(6)},
            utils.gen_str(): {utils.gen_str(): utils.gen_str() for _ in range(6)},
            utils.gen_str(): {utils.gen_str(): utils.gen_str() for _ in range(6)},
        }

        for key, artifact in six.viewitems(artifacts):
            experiment_run.log_artifact(key, artifact)
        for key, artifact in six.viewitems(artifacts):
            assert experiment_run.get_artifact(key) == artifact
        with pytest.raises(KeyError):
            experiment_run.get_artifact(utils.gen_str())

    def test_conflict(self, experiment_run):
        artifacts = {
            utils.gen_str(): {utils.gen_str(): utils.gen_str() for _ in range(6)},
            utils.gen_str(): {utils.gen_str(): utils.gen_str() for _ in range(6)},
            utils.gen_str(): {utils.gen_str(): utils.gen_str() for _ in range(6)},
        }

        for key, artifact in six.viewitems(artifacts):
            experiment_run.log_artifact(key, artifact)
            with pytest.raises(ValueError):
                experiment_run.log_artifact(key, artifact)

        for key, artifact in reversed(list(six.viewitems(artifacts))):
            with pytest.raises(ValueError):
                experiment_run.log_artifact(key, artifact)


class TestModels:
    def test_path(self, experiment_run):
        key = utils.gen_str()
        path = utils.gen_str()

        experiment_run.log_model_path(key, path)
        assert experiment_run.get_model(key) == path

    def test_store(self, experiment_run):
        key = utils.gen_str()
        model = sklearn.linear_model.LogisticRegression()

        experiment_run.log_model(key, model)
        assert experiment_run.get_model(key).get_params() == model.get_params()

    def test_conflict(self, experiment_run):
        models = {
            utils.gen_str(): sklearn.linear_model.LogisticRegression(),
            utils.gen_str(): sklearn.linear_model.LogisticRegression(),
            utils.gen_str(): sklearn.linear_model.LogisticRegression(),
        }

        for key, model in six.viewitems(models):
            experiment_run.log_model(key, model)
            with pytest.raises(ValueError):
                experiment_run.log_model(key, model)

        for key, model in reversed(list(six.viewitems(models))):
            with pytest.raises(ValueError):
                experiment_run.log_model(key, model)


class TestImages:
    @staticmethod
    def matplotlib_to_pil(fig):
        bytestream = six.BytesIO()
        fig.savefig(bytestream)
        return PIL.Image.open(bytestream)

    def test_path(self, experiment_run):
        key = utils.gen_str()
        path = utils.gen_str()

        experiment_run.log_image_path(key, path)
        assert experiment_run.get_image(key) == path

    def test_store_blank_warning(self, experiment_run):
        key = utils.gen_str()
        img = PIL.Image.new('RGB', (64, 64), 'white')

        with pytest.warns(UserWarning):
            experiment_run.log_image(key, img)

    def test_store_plt(self, experiment_run):
        key = utils.gen_str()
        plt.scatter(*np.random.random((2, 10)))

        experiment_run.log_image(key, plt)
        assert np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(self.matplotlib_to_pil(plt).getdata()))

    def test_store_fig(self, experiment_run):
        key = utils.gen_str()
        fig, ax = plt.subplots()
        ax.scatter(*np.random.random((2, 10)))

        experiment_run.log_image(key, fig)
        assert np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(self.matplotlib_to_pil(fig).getdata()))

    def test_store_pil(self, experiment_run):
        key = utils.gen_str()
        img = PIL.Image.new('RGB', (64, 64), 'white')
        PIL.ImageDraw.Draw(img).arc(np.r_[np.random.randint(32, size=(2)),
                                          np.random.randint(32, 64, size=(2))].tolist(),
                                    np.random.randint(360), np.random.randint(360),
                                    'black')

        experiment_run.log_image(key, img)
        assert(np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(img.getdata())))

    def test_conflict(self, experiment_run):
        images = {
            utils.gen_str(): PIL.Image.new('RGB', (64, 64), 'white'),
            utils.gen_str(): PIL.Image.new('RGB', (64, 64), 'purple'),
            utils.gen_str(): PIL.Image.new('RGB', (64, 64), 'green'),
        }

        for key, image in six.viewitems(images):
            experiment_run.log_image(key, image)
            with pytest.raises(ValueError):
                experiment_run.log_image(key, image)

        for key, image in reversed(list(six.viewitems(images))):
            with pytest.raises(ValueError):
                experiment_run.log_image(key, image)
