import six

import json
import os

import pytest

import verta
from verta import monitoring


class TestLogModelForDeployment:
    @pytest.mark.skipif(six.PY2, reason="run.get_model() doesn't work in Python 2")
    def test_model(self, experiment_run, model_for_deployment):
        experiment_run.log_model_for_deployment(**model_for_deployment)
        retrieved_model = experiment_run.get_model("model.pkl")

        assert model_for_deployment['model'].get_params() == retrieved_model.get_params()

    def test_model_api(self, experiment_run, model_for_deployment):
        experiment_run.log_model_for_deployment(**model_for_deployment)
        retrieved_model_api = verta.utils.ModelAPI.from_file(
            experiment_run.get_artifact("model_api.json"))

        assert all(item in six.viewitems(retrieved_model_api.to_dict())
                   for item in six.viewitems(model_for_deployment['model_api'].to_dict()))

    def test_reqs_on_disk(self, experiment_run, model_for_deployment, output_path):
        requirements_file = output_path.format("requirements.txt")
        with open(requirements_file, 'w') as f:
            f.write(model_for_deployment['requirements'].read())
        model_for_deployment['requirements'] = open(requirements_file, 'r')  # replace with on-disk file

        experiment_run.log_model_for_deployment(**model_for_deployment)
        retrieved_requirements = six.ensure_str(experiment_run.get_artifact("requirements.txt").read())

        with open(requirements_file, 'r') as f:
            assert set(f.read().split()) <= set(retrieved_requirements.split())

    def test_reqs_version_pins(self, experiment_run, model_for_deployment, output_path):
        """requirements must have exact version pins"""
        requirements_file = output_path.format("requirements.txt")
        with open(requirements_file, 'w') as f:
            # strip version number
            f.write('\n'.join(line.split('==')[0] for line in model_for_deployment['requirements'].read().splitlines()))
        model_for_deployment['requirements'] = open(requirements_file, 'r')  # replace with on-disk file

        with pytest.raises(ValueError):
            experiment_run.log_model_for_deployment(**model_for_deployment)

    def test_with_data(self, experiment_run, model_for_deployment):
        """`train_features` and `train_targets` have associated data processors"""
        experiment_run.log_model_for_deployment(**model_for_deployment)

        # check feature DataFrame processors
        for col_name in model_for_deployment['train_features']:
            processor_key = "data-processor--{}".format(col_name)
            assert isinstance(experiment_run.get_artifact(processor_key), monitoring._BaseProcessor)

        # check label Series processor
        col_name = model_for_deployment['train_targets'].name
        processor_key = "data-processor--{}".format(col_name)
        assert isinstance(experiment_run.get_artifact(processor_key), monitoring._BaseProcessor)
