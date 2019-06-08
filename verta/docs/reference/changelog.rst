Release Notes
=============


v0.11.6 (2019-06-07)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `Providing a cloudpickle version in the requirements for deployment that doesn't match the version used by the Client
  now raises an error instead of overwriting the line in the requirements.
  <https://github.com/VertaAI/modeldb-client/commit/871bef8dc92a01e6516ee7d13b5b3035e9bbd5bc>`_

New Features
^^^^^^^^^^^^
- `add ExperimentRun's Verta WebApp URL to its __repr__()
  <https://github.com/VertaAI/modeldb-client/pull/108>`_

Bug Fixes
^^^^^^^^^
- `use cloudpickle.__version__ instead of relying on pip
  <https://github.com/VertaAI/modeldb-client/commit/82c0f8200a62caffcf825e4b399ccbce3bfdac2c>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `remove internal utility get_env_dependencies()
  <https://github.com/VertaAI/modeldb-client/commit/ce333bc7b1cf2587e03e668987ca1066062b2cd5>`_
- `update notebooks
  <https://github.com/VertaAI/modeldb-client/commit/0003f31298910d301e586ddd77328263e9830580>`_


v0.11.5 (2019-06-04)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `The dataset_csv parameter for log_model_for_deployment() has been replaced with two parameters for feature and target
  DataFrames.
  <https://github.com/VertaAI/modeldb-client/commit/4d113552916d3999e220fd0e3964658487df6925>`_

Bug Fixes
^^^^^^^^^
- `properly render lists in docstrings
  <https://github.com/VertaAI/modeldb-client/commit/4f5c6c2b0fe7b58c1c8c039d589505a050ad09c2>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `have the upload script clean out build directories after uploading
  <https://github.com/VertaAI/modeldb-client/commit/9d78662c53e6d0ad1e76ed2708e8ac0b8d0de2bc>`_


v0.11.4 (2019-05-31)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `The dataset_df parameter for log_model_for_deployment() has been renamed to dataset_csv.
  <https://github.com/VertaAI/modeldb-client/commit/ea49d069d8825375f8988dfcebb882b7489ed1a8>`_

Bug Fixes
^^^^^^^^^
- `reset the correct streams in log_model_for_deployment() instead of model_api over and over again
  <https://github.com/VertaAI/modeldb-client/commit/d12fb6bbad058b1e9495af19bec1ecca86c777c4>`_


v0.11.3 (2019-05-31)
--------------------

New Features
^^^^^^^^^^^^
- `implement __version__ attribute on package
  <https://github.com/VertaAI/modeldb-client/commit/31aee4b53aeb6652831e560b9f475fb09d7cc8b4>`_

Bug Fixes
^^^^^^^^^
- `remove unsupported dependency on pandas and NumPy in utils module
  <https://github.com/VertaAI/modeldb-client/commit/659ceca31cb54ca461780d7f2109df8045b3442e>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `move package version string from verta/setup.py to verta/verta/__about__.py
  <https://github.com/VertaAI/modeldb-client/commit/31aee4b53aeb6652831e560b9f475fb09d7cc8b4>`_
- `remove old model API tests that have been superseded by property-based tests
  <https://github.com/VertaAI/modeldb-client/commit/4a0c7995cb7df67060daa7162146b4eaffe28137>`_
- `add pandas as a testing dependency
  <https://github.com/VertaAI/modeldb-client/commit/cc47d851a1eecf9277939cda2bbd12e3834b3ec3>`_


v0.11.2 (2019-05-30)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `Parameters for Client.set_* functions have been renamed to name and id, from e.g. proj_name and _proj_id.
  <https://github.com/VertaAI/modeldb-client/commit/889130d6ccf224b6de085a6a473993c5d9a16765>`_
- `The _id attribute of Project, Experiment, and ExperimentRun have been renamed to id.
  <https://github.com/VertaAI/modeldb-client/commit/eb832fbf86e1c403a1683b8e02fb8b6a47c06d82>`_
- `The default generated names for Project, Experiment, and ExperimentRun have been shortened.
  <https://github.com/VertaAI/modeldb-client/commit/3e515abf4bc4b68560479039ce95550ea451e3e7>`_

Bug Fixes
^^^^^^^^^
- `fix typos in Client.set_* error messages
  <https://github.com/VertaAI/modeldb-client/commit/0b8e4f99d1dbe26718a5d151f53fbfba93b19d38>`_


v0.11.1 (2019-05-29)
--------------------

Bug Fixes
^^^^^^^^^
- `fix internal utility get_env_dependencies() for compatibility with Python 3.6 and earlier
  <https://github.com/VertaAI/modeldb-client/commit/03b4005e44bddedf857dc59e7583eb57b8c529a5>`_


v0.11.0 (2019-05-29)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `log_model_for_deployment() now no longer requires a dataset argument, but requires a model API argument. The order
  of parameters has changed, and dataset_csv has been renamed to dataset_df.
  <https://github.com/VertaAI/modeldb-client/pull/99>`_

New Features
^^^^^^^^^^^^
- `implement ModelAPI utility class for generating model APIs
  <https://github.com/VertaAI/modeldb-client/pull/102>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `create an example notebook that downloads our beloved Census data with wget
  <https://github.com/VertaAI/modeldb-client/blob/b998b6be7209f217436b630ebd44eb74df4e37a7/workflows/examples-without-verta/notebooks/sklearn-census.ipynb>`_
- `rename the "scikit" model type to "sklearn"
  <https://github.com/VertaAI/modeldb-client/pull/102>`_
- `delete old internal model API generation utility
  <https://github.com/VertaAI/modeldb-client/pull/102>`_
- `update demo utility predict function to simply dump the JSON input into the request body
  <https://github.com/VertaAI/modeldb-client/commit/094494da3c89ae16064849e1af670020cebec4f8#diff-5ecfc26883949a5768007510d498b950>`_
- `implement internal utility to check for exact version pins in a requirements.txt
  <https://github.com/VertaAI/modeldb-client/pull/100>`_
- `implement internal utility to obtain the local environment's Python version number
  <https://github.com/VertaAI/modeldb-client/pull/98>`_
- `update READMEs
  <https://github.com/VertaAI/modeldb-client/commit/f0579f2cbdee69f411b2481ae249b87b35d07383>`_
- `add utils module to API reference
  <https://github.com/VertaAI/modeldb-client/commit/f83a20396ee2a215d6a7419b5fe96ea158d91655>`_
- `implement tests for model API generation
  <https://github.com/VertaAI/modeldb-client/commit/5982221b8d88ee40b400813955d123321519f1ff>`_
- `implement property-based tests for model API generation
  <https://github.com/VertaAI/modeldb-client/commit/d3e2a588cc95c9fe91382dbc7fa34052e6f707d7>`_
- `add deepdiff to testing requirements
  <https://github.com/VertaAI/modeldb-client/commit/4edf10b41050d77ccc044068184889579a1c4c57>`_
- `add hypothesis to testing requirements
  <https://github.com/VertaAI/modeldb-client/commit/8044b6ac525e831bdff58fe21b1bdb261e920796>`_


v0.10.2 (2019-05-22)
--------------------
no functional changes


v0.10.1 (2019-05-22)
--------------------

Bug Fixes
^^^^^^^^^
- `properly expose intermediate subpackages for compatibility with Python 3.2 and earlier
  <https://github.com/VertaAI/modeldb-client/commit/d3037ac5670c022c2f2aa4b1f50b49e9c19646b0>`_


v0.10.0 (2019-05-16)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `log_hyperparameters() now must take a single, whole dictionary as an argument and no longer accepts dictionary
  unpacking.
  <https://github.com/VertaAI/modeldb-client/pull/96>`_
- `Getting observations from an ExperimentRun now returns tuples pairing observations with their timestamps.
  <https://github.com/VertaAI/modeldb-client/pull/83>`_
- `Passing a string into artifact logging functions now attempts to open a file located at the path represented by that
  string, rather than simply logging the string itself.
  <https://github.com/VertaAI/modeldb-client/pull/94>`_
- `Attempting to log an unsupported datatype now throws a TypeError instead of a ValueError.
  <https://github.com/VertaAI/modeldb-client/pull/90/files>`_
- `Logging artifacts now uses cloudpickle by default, instead of pickle.
  <https://github.com/VertaAI/modeldb-client/pull/90/files>`_
- `The internal logic for getting a Project by name has changed, and will be incompatible with old versions of the Verta
  Back End.
  <https://github.com/VertaAI/modeldb-client/commit/595b70749b585f13a38afef6b91b4aeae633c5ae>`_
- `The internal logic for handling uploading custom models for deployment has changed, and will be incompatible with old
  versions of the Verta Back End.
  <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `The internal logic for getting an ExperimentRun by name has changed, and may be incompatible with old versions of the
  Verta Back End.
  <https://github.com/VertaAI/modeldb-client/pull/89>`_

New Features
^^^^^^^^^^^^
- `associate user-specified or automatically-generated timestamps with observations
  <https://github.com/VertaAI/modeldb-client/pull/83>`_
- `implement methods on ExperimentRun for logging and getting tags
  <https://github.com/VertaAI/modeldb-client/pull/84/files>`_
- `implement methods on ExperimentRun for logging multiple attributes, metrics, or hyperparameters in a single transaction
  <https://github.com/VertaAI/modeldb-client/pull/87>`_
- `enable uploading custom model APIs for deployment
  <https://github.com/VertaAI/modeldb-client/pull/91>`_
- `create functions specifically for logging artifact paths without attempting uploads
  <https://github.com/VertaAI/modeldb-client/pull/94>`_

Bug Fixes
^^^^^^^^^
- `reset stream pointer on failed deserialization attempts
  <https://github.com/VertaAI/modeldb-client/pull/86>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `convert pandas DataFrames into CSVs when logging for deployment for data monitoring
  <https://github.com/VertaAI/modeldb-client/pull/85>`_
- `implement a secondary predict function in demo utilities that returns the raw HTML response instead of a formatted
  response
  <https://github.com/VertaAI/modeldb-client/pull/92>`_
- `move our example notebooks from workflows/demos/ to workflows/examples/
  <https://github.com/VertaAI/modeldb-client/commit/de197f6821ccbb904a4cd1e45b66b45e5c7f68a6>`_
- `change "unknown" model type to "custom" in model API
  <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `add "keras" deserialization in model API
  <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `add cloudpickle to requirements with the locally pinned version if it was used when logging for deployment
  <https://github.com/VertaAI/modeldb-client/pull/95>`_
- `implement handful of small fixes to maintain Python 2.7 compatibility
  <https://github.com/VertaAI/modeldb-client/pull/97>`_
