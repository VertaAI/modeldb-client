import six

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

        experiment_run.log_artifact(key, path)
        assert experiment_run.get_artifact(key) == path

    def test_store(self, experiment_run):
        key = utils.gen_str()
        artifact = {utils.gen_str(): utils.gen_str() for _ in range(6)}

        experiment_run.log_artifact(key, artifact)
        assert experiment_run.get_artifact(key) == artifact

    def test_empty(self, experiment_run):
        artifacts = {
            utils.gen_str(): "",
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


class TestDatasets:
    def test_path(self, experiment_run):
        key = utils.gen_str()
        path = utils.gen_str()

        experiment_run.log_dataset(key, path)
        assert experiment_run.get_dataset(key) == path

    def test_store(self, experiment_run):
        key = utils.gen_str()
        dataset = np.random.random(size=(36,6))

        experiment_run.log_dataset(key, dataset)
        assert np.array_equal(experiment_run.get_dataset(key), dataset)


class TestModels:
    def test_path(self, experiment_run):
        key = utils.gen_str()
        path = utils.gen_str()

        experiment_run.log_model(key, path)
        assert experiment_run.get_model(key) == path

    def test_store(self, experiment_run):
        key = utils.gen_str()
        model = sklearn.linear_model.LogisticRegression()

        experiment_run.log_model(key, model)
        assert experiment_run.get_model(key).get_params() == model.get_params()


class TestImages:
    @staticmethod
    def matplotlib_to_pil(fig):
        bytestream = six.BytesIO()
        fig.savefig(bytestream)
        return PIL.Image.open(bytestream)

    def test_path(self, experiment_run):
        key = utils.gen_str()
        path = utils.gen_str()

        experiment_run.log_image(key, path)
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
                                    *np.random.randint(360, size=2),
                                    'black')

        experiment_run.log_image(key, img)
        assert(np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(img.getdata())))