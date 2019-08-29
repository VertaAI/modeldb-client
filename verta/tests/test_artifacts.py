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
import sklearn
from sklearn import cluster, naive_bayes, pipeline, preprocessing
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

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
    def test_sklearn(self, seed, experiment_run, strs):
        np.random.seed(seed)
        key = strs[0]
        num_data_rows = 36
        X = np.random.random((num_data_rows, 2))
        y = np.random.randint(10, size=num_data_rows)

        pipeline = sklearn.pipeline.make_pipeline(
            sklearn.preprocessing.StandardScaler(),
            sklearn.cluster.KMeans(),
            sklearn.naive_bayes.GaussianNB(),
        )
        pipeline.fit(X, y)

        experiment_run.log_model(key, pipeline)
        retrieved_pipeline = experiment_run.get_model(key)

        assert np.allclose(pipeline.predict(X), retrieved_pipeline.predict(X))

        assert len(pipeline.steps) == len(retrieved_pipeline.steps)
        for step, retrieved_step in zip(pipeline.steps, retrieved_pipeline.steps):
            assert step[0] == retrieved_step[0]  # step name
            assert step[1].get_params() == retrieved_step[1].get_params()  # step model

    def test_torch(self, seed, experiment_run, strs):
        np.random.seed(seed)
        key = strs[0]
        num_data_rows = 36
        X = torch.tensor(np.random.random((num_data_rows, 3, 32, 32)), dtype=torch.float)

        class Model(nn.Module):
            def __init__(self):
                super(Model, self).__init__()
                self.conv1 = nn.Conv2d(3, 6, 5)
                self.pool = nn.MaxPool2d(2, 2)
                self.conv2 = nn.Conv2d(6, 16, 5)
                self.fc1 = nn.Linear(16 * 5 * 5, 120)
                self.fc2 = nn.Linear(120, 84)
                self.fc3 = nn.Linear(84, 10)

            def forward(self, x):
                x = self.pool(F.relu(self.conv1(x)))
                x = self.pool(F.relu(self.conv2(x)))
                x = x.view(-1, 16 * 5 * 5)
                x = F.relu(self.fc1(x))
                x = F.relu(self.fc2(x))
                x = self.fc3(x)
                return x

        net = Model()

        experiment_run.log_model(key, net)
        retrieved_net = experiment_run.get_model(key)

        assert torch.allclose(net(X), retrieved_net(X))

        assert net.state_dict().keys() == retrieved_net.state_dict().keys()
        for key, weight in net.state_dict().items():
            assert torch.allclose(weight, retrieved_net.state_dict()[key])

    def test_keras(self, experiment_run, strs):
        raise NotImplementedError
        key = strs[0]

    def test_no_tensorflow(self, experiment_run, strs):
        raise NotImplementedError
        key = strs[0]

    def test_function(self, experiment_run, strs, flat_lists, flat_dicts):
        key = strs[0]
        func_args = flat_lists[0]
        func_kwargs = flat_dicts[0]

        def func(is_func=True, _cache=set([1, 2, 3]), *args, **kwargs):
            return (args, kwargs)

        experiment_run.log_model(key, func)
        assert experiment_run.get_model(key).__defaults__ == func.__defaults__
        assert experiment_run.get_model(key)(*func_args, **func_kwargs) == func(*func_args, **func_kwargs)

    def test_custom_class(self, experiment_run, strs, flat_lists, flat_dicts):
        key = strs[0]
        init_args = flat_lists[0]
        init_kwargs = flat_dicts[0]

        class Custom:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def predict(self, data):
                return (self.args, self.kwargs)

        custom = Custom(*init_args, **init_kwargs)

        experiment_run.log_model(key, custom)
        assert experiment_run.get_model(key).__dict__ == custom.__dict__
        assert experiment_run.get_model(key).predict(strs) == custom.predict(strs)


class TestImages:
    @staticmethod
    def matplotlib_to_pil(fig):
        bytestream = six.BytesIO()
        fig.savefig(bytestream)
        return PIL.Image.open(bytestream)

    def test_log_path(self, experiment_run, strs):
        strs, holdout = strs[:-1], strs[-1]  # reserve last key

        for key, image_path in zip(strs, strs):
            experiment_run.log_image_path(key, image_path)

        for key, image_path in zip(strs, strs):
            assert experiment_run.get_image(key) == image_path

        with pytest.raises(KeyError):
            experiment_run.get_image(holdout)

    def test_upload_blank_warning(self, experiment_run, strs):
        key = strs[0]
        img = PIL.Image.new('RGB', (64, 64), 'white')

        with pytest.warns(UserWarning):
            experiment_run.log_image(key, img)

    def test_upload_plt(self, experiment_run, strs):
        key = strs[0]
        plt.scatter(*np.random.random((2, 10)))

        experiment_run.log_image(key, plt)
        assert np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(self.matplotlib_to_pil(plt).getdata()))

    def test_upload_fig(self, experiment_run, strs):
        key = strs[0]
        fig, ax = plt.subplots()
        ax.scatter(*np.random.random((2, 10)))

        experiment_run.log_image(key, fig)
        assert np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(self.matplotlib_to_pil(fig).getdata()))

    def test_upload_pil(self, experiment_run, strs):
        key = strs[0]
        img = PIL.Image.new('RGB', (64, 64), 'gray')
        PIL.ImageDraw.Draw(img).arc(np.r_[np.random.randint(32, size=(2)),
                                          np.random.randint(32, 64, size=(2))].tolist(),
                                    np.random.randint(360), np.random.randint(360),
                                    'white')

        experiment_run.log_image(key, img)
        assert(np.array_equal(np.asarray(experiment_run.get_image(key).getdata()),
                              np.asarray(img.getdata())))

    def test_conflict(self, experiment_run, strs):
        images = dict(zip(strs, [PIL.Image.new('RGB', (64, 64), 'gray')]*3))

        for key, image in six.viewitems(images):
            experiment_run.log_image(key, image)
            with pytest.raises(ValueError):
                experiment_run.log_image(key, image)

        for key, image in reversed(list(six.viewitems(images))):
            with pytest.raises(ValueError):
                experiment_run.log_image(key, image)
