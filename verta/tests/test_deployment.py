import pytest

import six

import json
import os
import tempfile

import verta


@pytest.fixture
def model_for_deployment(strs):
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")
    sklearn = pytest.importorskip("sklearn")
    from sklearn import linear_model

    num_rows, num_cols = 36, 6

    data = pd.DataFrame(np.tile(np.arange(num_rows).reshape(-1, 1),
                                num_cols),
                        columns=strs[:num_cols])
    X_train = data.iloc[:,:-1]  # pylint: disable=bad-whitespace
    y_train = data.iloc[:, -1]

    return {
        'model': sklearn.linear_model.LogisticRegression(),
        'model_api': verta.utils.ModelAPI(X_train, y_train),
        'requirements': six.StringIO("scikit-learn=={}".format(sklearn.__version__)),
        'train_features': X_train,
        'train_targets': y_train,
    }


class TestLogModelForDeployment:
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
        """`train_features` and `train_targets` are joined into a single CSV"""
        experiment_run.log_model_for_deployment(**model_for_deployment)

        data_csv = experiment_run.get_artifact("train_data").read()

        X_train = model_for_deployment['train_features']
        y_train = model_for_deployment['train_targets']
        assert X_train.join(y_train).to_csv(index=False) == six.ensure_str(data_csv)


class TestLogRequirements:
    NONSPECIFIC_REQ = "verta>0.1.0"
    INVALID_REQ = "@==1.2.3"
    UNIMPORTABLE_REQ = "bananacoconut"
    VERTA_MISMATCH_REQ = "verta==0.0.0"
    CLOUDPICKLE_MISMATCH_REQ = "cloudpickle==0.0.0"
    VALID_REQS = [
        'cloudpickle',
        'pytest',
        'verta',
    ]

    def test_nonspecific_ver_list_warning(self, experiment_run):
        with pytest.warns(UserWarning):
            experiment_run.log_requirements([self.NONSPECIFIC_REQ])

    def test_nonspecific_ver_file_warning(self, experiment_run):
        with tempfile.NamedTemporaryFile('w+') as tempf:
            tempf.write(self.NONSPECIFIC_REQ)
            tempf.seek(0)

            with pytest.warns(UserWarning):
                experiment_run.log_requirements(tempf.name)

    def test_invalid_pkg_name_list_error(self, experiment_run):
        with pytest.raises(ValueError):
            experiment_run.log_requirements([self.INVALID_REQ])

    def test_invalid_pkg_name_file_error(self, experiment_run):
        with tempfile.NamedTemporaryFile('w+') as tempf:
            tempf.write(self.INVALID_REQ)
            tempf.seek(0)

            with pytest.raises(ValueError):
                experiment_run.log_requirements(tempf.name)

    def test_unimportable_pkg_list_error(self, experiment_run):
        with pytest.raises(ValueError):
            experiment_run.log_requirements([self.UNIMPORTABLE_REQ])

    def test_unimportable_pkg_file_error(self, experiment_run):
        with tempfile.NamedTemporaryFile('w+') as tempf:
            tempf.write(self.UNIMPORTABLE_REQ)
            tempf.seek(0)

            with pytest.raises(ValueError):
                experiment_run.log_requirements(tempf.name)

    def test_verta_ver_mismatch_list_error(self, experiment_run):
        with pytest.raises(ValueError):
            experiment_run.log_requirements([self.VERTA_MISMATCH_REQ])

    def test_verta_ver_mismatch_file_error(self, experiment_run):
        with tempfile.NamedTemporaryFile('w+') as tempf:
            tempf.write(self.VERTA_MISMATCH_REQ)
            tempf.seek(0)

            with pytest.raises(ValueError):
                experiment_run.log_requirements(tempf.name)

    def test_cloudpickle_ver_mismatch_list_error(self, experiment_run):
        with pytest.raises(ValueError):
            experiment_run.log_requirements([self.CLOUDPICKLE_MISMATCH_REQ])

    def test_cloudpickle_ver_mismatch_file_error(self, experiment_run):
        with tempfile.NamedTemporaryFile('w+') as tempf:
            tempf.write(self.CLOUDPICKLE_MISMATCH_REQ)
            tempf.seek(0)

            with pytest.raises(ValueError):
                experiment_run.log_requirements(tempf.name)

    def test_injection_list(self, experiment_run):
        experiment_run.log_requirements([])

        reqs_txt = experiment_run.get_artifact("requirements.txt").read().decode()
        reqs = set(req.split('==')[0].strip() for req in reqs_txt.splitlines())
        assert {'cloudpickle', 'verta'} == reqs

    def test_injection_file(self, experiment_run):
        with tempfile.NamedTemporaryFile('w+') as tempf:
            experiment_run.log_requirements(tempf.name)

        reqs_txt = experiment_run.get_artifact("requirements.txt").read().decode()
        reqs = set(req.split('==')[0].strip() for req in reqs_txt.splitlines())
        assert {'cloudpickle', 'verta'} == reqs

    def test_list(self, experiment_run):
        experiment_run.log_requirements(self.VALID_REQS)

        reqs_txt = experiment_run.get_artifact("requirements.txt").read().decode()
        reqs = set(req.split('==')[0].strip() for req in reqs_txt.splitlines())
        assert set(self.VALID_REQS) == reqs

    def test_file(self, experiment_run):
        with tempfile.NamedTemporaryFile('w+') as tempf:
            tempf.write('\n'.join(self.VALID_REQS))
            tempf.seek(0)

            experiment_run.log_requirements(tempf.name)

        reqs_txt = experiment_run.get_artifact("requirements.txt").read().decode()
        reqs = set(req.split('==')[0].strip() for req in reqs_txt.splitlines())
        assert set(self.VALID_REQS) == reqs
