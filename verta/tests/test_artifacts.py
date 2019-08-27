import six

import os
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
    def test_log_path(self, experiment_run, strs):
        strs, holdout = strs[:-1], strs[-1]  # reserve last key

        for key, artifact_path in zip(strs, strs):
            experiment_run.log_artifact_path(key, artifact_path)

        for key, artifact_path in zip(strs, strs):
            assert experiment_run.get_artifact(key) == artifact_path

        with pytest.raises(KeyError):
            experiment_run.get_artifact(holdout)

    def test_upload_object(self, experiment_run, strs, all_values):
        strs, holdout = strs[:-1], strs[-1]  # reserve last key
        all_values = (value  # log_artifact treats str value as filepath to open
                      for value in all_values if not isinstance(value, str))

        for key, artifact in zip(strs, all_values):
            experiment_run.log_artifact(key, artifact)

        for key, artifact in zip(strs, all_values):
            assert experiment_run.get_artifact(key) == artifact

        with pytest.raises(KeyError):
            experiment_run.get_artifact(holdout)

    def test_upload_file(self, experiment_run, strs):
        filepaths = (filepath for filepath in os.listdir() if filepath.endswith('.py'))
        artifacts = list(zip(strs, filepaths))

        # log using file handle
        for key, artifact_filepath in artifacts[:len(artifacts)//2]:
            with open(artifact_filepath, 'r') as artifact_file:  # does not need to be 'rb'
                experiment_run.log_artifact(key, artifact_file)

        # log using filepath
        for key, artifact_filepath in artifacts[len(artifacts)//2:]:
            experiment_run.log_artifact(key, artifact_filepath)

        # get
        for key, artifact_filepath in artifacts:
            with open(artifact_filepath, 'rb') as artifact_file:
                assert experiment_run.get_artifact(key).read() == artifact_file.read()

    def test_empty(self, experiment_run, strs):
        """uploading empty data, e.g. an empty file, raises an error"""

        with pytest.raises(ValueError):
            experiment_run.log_artifact(strs[0], six.BytesIO())

    def test_conflict(self, experiment_run, strs, all_values):
        all_values = (value  # log_artifact treats str value as filepath to open
                      for value in all_values if not isinstance(value, str))

        for key, artifact in zip(strs, all_values):
            experiment_run.log_artifact(key, artifact)
            with pytest.raises(ValueError):
                experiment_run.log_artifact(key, artifact)

        for key, artifact in reversed(list(zip(strs, all_values))):
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
        img = PIL.Image.new('RGB', (64, 64), 'gray')
        PIL.ImageDraw.Draw(img).arc(np.r_[np.random.randint(32, size=(2)),
                                          np.random.randint(32, 64, size=(2))].tolist(),
                                    np.random.randint(360), np.random.randint(360),
                                    'white')

        experiment_run.log_image(key, img)
        assert(np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(img.getdata())))

    def test_conflict(self, experiment_run):
        images = {
            utils.gen_str(): PIL.Image.new('RGB', (64, 64), 'gray'),
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
