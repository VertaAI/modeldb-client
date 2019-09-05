import six

import json
import os

import pytest

import verta


class TestLogModelForDeployment:
    def test_model(self, experiment_run, model_for_deployment):
        model, _, _, _, _ = model_for_deployment

        experiment_run.log_model_for_deployment(*model_for_deployment)
        retrieved_model = experiment_run.get_model("model.pkl")

        assert model.get_params() == retrieved_model.get_params()

    def test_model_api(self, experiment_run, model_for_deployment):
        _, model_api, _, _, _ = model_for_deployment

        experiment_run.log_model_for_deployment(*model_for_deployment)
        retrieved_model_api = verta.utils.ModelAPI.from_file(
            experiment_run.get_artifact("model_api.json"))

        assert all(item in six.viewitems(retrieved_model_api.to_dict())
                   for item in six.viewitems(model_api.to_dict()))

    def test_reqs_on_disk(self, experiment_run, model_for_deployment, output_path):
        model, model_api, requirements, _, _ = model_for_deployment
        requirements_file = output_path.format("requirements.txt")

        with open(requirements_file, 'w') as f:
            f.write(requirements.read())
            requirements.seek(0)

        experiment_run.log_model_for_deployment(model, model_api, open(requirements_file, 'r'))
        retrieved_requirements = six.ensure_str(experiment_run.get_artifact("requirements.txt").read())

        requirements = requirements.read()
        assert set(requirements.split()) <= set(retrieved_requirements.split())

    def test_reqs_version_pins(self, experiment_run, model_for_deployment, output_path):
        """requirements must have exact version pins"""
        model, model_api, requirements, _, _ = model_for_deployment
        requirements_file = output_path.format("requirements.txt")

        with open(requirements_file, 'w') as f:
            f.write(requirements.read().split('==')[0])  # strip version number

        with pytest.raises(ValueError):
            experiment_run.log_model_for_deployment(model, model_api, open(requirements_file, 'r'))

    def test_with_data(self, experiment_run, model_for_deployment):
        """`train_features` and `train_targets` are joined into a single CSV"""
        _, _, _, X_train, y_train = model_for_deployment

        experiment_run.log_model_for_deployment(*model_for_deployment)

        data_csv = experiment_run.get_artifact("train_data")
        assert X_train.join(y_train).to_csv(index=False) == six.ensure_str(data_csv.read())
