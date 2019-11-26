import pytest

import six

import json
import os
import sys
import tempfile
import zipfile

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


@pytest.fixture
def model_packaging():
    """Additional items added to model API in log_model()."""
    return {
        'python_version': verta._utils.get_python_version(),
        'type': "sklearn",
        'deserialization': "cloudpickle",
    }


class TestLogModelForDeployment:
    def test_model(self, experiment_run, model_for_deployment):
        experiment_run.log_model_for_deployment(**model_for_deployment)
        retrieved_model = experiment_run.get_model()

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

    def test_with_data(self, experiment_run, model_for_deployment):
        """`train_features` and `train_targets` are joined into a single CSV"""
        experiment_run.log_model_for_deployment(**model_for_deployment)

        data_csv = experiment_run.get_artifact("train_data").read()

        X_train = model_for_deployment['train_features']
        y_train = model_for_deployment['train_targets']
        assert X_train.join(y_train).to_csv(index=False) == six.ensure_str(data_csv)


class TestLogModel:
    def test_model(self, experiment_run, model_for_deployment):
        experiment_run.log_model(model_for_deployment['model'])

        assert model_for_deployment['model'].get_params() == experiment_run.get_model().get_params()

    def test_custom_modules(self, experiment_run, model_for_deployment):
        custom_modules_dir = "."

        experiment_run.log_model(
            model_for_deployment['model'],
            custom_modules=["."],
        )

        custom_module_filenames = {"__init__.py", "_verta_config.py"}
        for parent_dir, dirnames, filenames in os.walk(custom_modules_dir):
            # skip venvs
            exec_path = os.path.join(parent_dir, "{}", "bin", "python")  # from verta._utils.find_filepaths()
            dirnames[:] = [dirname for dirname in dirnames if not os.path.lexists(exec_path.format(dirname))]

            custom_module_filenames.update(map(os.path.basename, filenames))

        with zipfile.ZipFile(experiment_run.get_artifact("custom_modules"), 'r') as zipf:
            assert custom_module_filenames == set(map(os.path.basename, zipf.namelist()))

    def test_no_custom_modules(self, experiment_run, model_for_deployment):
        experiment_run.log_model(model_for_deployment['model'])

        custom_module_filenames = {"__init__.py", "_verta_config.py"}
        for path in sys.path:
            # skip std libs and Jupyter libs
            if (not path
                    or verta.client.PY_DIR_REGEX.search(path)
                    or verta.client.PY_ZIP_REGEX.search(path)
                    or verta.client.IPYTHON_REGEX.search(path)):
                continue

            for parent_dir, dirnames, filenames in os.walk(path):
                # skip venvs
                exec_path = os.path.join(parent_dir, "{}", "bin", "python")  # from verta._utils.find_filepaths()
                dirnames[:] = [dirname for dirname in dirnames if not os.path.lexists(exec_path.format(dirname))]

                # only Python files
                filenames[:] = [filename for filename in filenames if filename.endswith(('.py', '.pyc', '.pyo'))]

                custom_module_filenames.update(map(os.path.basename, filenames))

        with zipfile.ZipFile(experiment_run.get_artifact("custom_modules"), 'r') as zipf:
            assert custom_module_filenames == set(map(os.path.basename, zipf.namelist()))

    def test_model_api(self, experiment_run, model_for_deployment, model_packaging):
        experiment_run.log_model(
            model_for_deployment['model'],
            model_api=model_for_deployment['model_api'],
        )

        model_api = model_for_deployment['model_api'].to_dict()
        model_api.update({
            'model_packaging': model_packaging,
        })
        assert model_api == json.loads(six.ensure_str(experiment_run.get_artifact('model_api.json').read()))

    def test_no_model_api(self, experiment_run, model_for_deployment, model_packaging):
        experiment_run.log_model(model_for_deployment['model'])

        model_api = {
            'version': "v1",
            'model_packaging': model_packaging,
        }
        assert model_api == json.loads(six.ensure_str(experiment_run.get_artifact('model_api.json').read()))

    def test_model_class(self, experiment_run, model_for_deployment):
        experiment_run.log_model(model_for_deployment['model'].__class__)

        assert model_for_deployment['model'].__class__ == experiment_run.get_model()

        retrieved_model_api = verta.utils.ModelAPI.from_file(experiment_run.get_artifact("model_api.json"))
        assert retrieved_model_api.to_dict()['model_packaging']['type'] == "class"

    def test_artifacts(self, experiment_run, model_for_deployment, strs, flat_dicts):
        for key, artifact in zip(strs, flat_dicts):
            experiment_run.log_artifact(key, artifact)

        experiment_run.log_model(
            model_for_deployment['model'].__class__,
            artifacts=strs,
        )

        assert experiment_run.get_attribute("verta_model_artifacts") == strs

    def test_no_artifacts(self, experiment_run, model_for_deployment):
        experiment_run.log_model(model_for_deployment['model'].__class__)

        with pytest.raises(KeyError):
            experiment_run.get_attribute("verta_model_artifacts")

    def test_wrong_type_artifacts_error(self, experiment_run, model_for_deployment, all_values):
        # remove Nones, because they're equivalent to unprovided
        all_values = [val for val in all_values
                      if val is not None]
        # remove lists of strings and empty lists, because they're valid arguments
        all_values = [val for val in all_values
                      if not (isinstance(val, list) and all(isinstance(el, six.string_types) for el in val))]

        for val in all_values:
            with pytest.raises(TypeError):
                experiment_run.log_model(
                    model_for_deployment['model'].__class__,
                    artifacts=val,
                )

    def test_not_class_model_artifacts_error(self, experiment_run, model_for_deployment, strs, flat_dicts):
        for key, artifact in zip(strs, flat_dicts):
            experiment_run.log_artifact(key, artifact)

        with pytest.raises(ValueError):
            experiment_run.log_model(
                model_for_deployment['model'],
                artifacts=strs,
            )

    def test_unlogged_keys_artifacts_error(self, experiment_run, model_for_deployment, strs, flat_dicts):
        with pytest.raises(ValueError):
            experiment_run.log_model(
                model_for_deployment['model'],
                artifacts=[strs[0]],
            )

        experiment_run.log_artifact(strs[0], flat_dicts[0])

        with pytest.raises(ValueError):
            experiment_run.log_model(
                model_for_deployment['model'],
                artifacts=[strs[1]],
            )

        with pytest.raises(ValueError):
            experiment_run.log_model(
                model_for_deployment['model'],
                artifacts=strs[1:],
            )


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


class TestLogTrainingData:
    def test_numpy_error(self, experiment_run, model_for_deployment):
        with pytest.raises(TypeError):
            experiment_run.log_training_data(
                model_for_deployment['train_features'].values,
                model_for_deployment['train_targets'].values,
            )

    def test_list_error(self, experiment_run, model_for_deployment):
        with pytest.raises(TypeError):
            experiment_run.log_training_data(
                model_for_deployment['train_features'].values.tolist(),
                model_for_deployment['train_targets'].values.tolist(),
            )

    def test_column_name_error(self, experiment_run, model_for_deployment):
        X_train = model_for_deployment['train_features']
        y_train = model_for_deployment['train_targets']

        y_train = y_train.rename(X_train.columns[0])

        with pytest.raises(ValueError):
            experiment_run.log_training_data(X_train, y_train)

    def test_series(self, experiment_run, model_for_deployment):
        X_train = model_for_deployment['train_features']
        y_train = model_for_deployment['train_targets']

        experiment_run.log_training_data(X_train, y_train)

        data_csv = experiment_run.get_artifact("train_data").read()
        assert X_train.join(y_train).to_csv(index=False) == six.ensure_str(data_csv)

    def test_dataframe(self, experiment_run, model_for_deployment):
        X_train = model_for_deployment['train_features']
        y_train = model_for_deployment['train_targets']

        y_train = y_train.to_frame()

        experiment_run.log_training_data(X_train, y_train)

        data_csv = experiment_run.get_artifact("train_data").read()
        assert X_train.join(y_train).to_csv(index=False) == six.ensure_str(data_csv)
