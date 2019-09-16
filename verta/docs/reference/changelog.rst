Release Notes
=============


.. This comment block is a template for version release notes.
   v.. (--)
   --------------------

   Backwards Incompatibilities
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
   - `
     <>`_

   Deprecations
   ^^^^^^^^^^^^
   - `
     <>`_

   New Features
   ^^^^^^^^^^^^
   - `
     <>`_

   Bug Fixes
   ^^^^^^^^^
   - `
     <>`_

   Internal Changes
   ^^^^^^^^^^^^^^^^
   - `
     <>`_


v0.13.7 (2019-09-18)
--------------------

New Features
^^^^^^^^^^^^
- `accept key prefixes for S3DatasetVersion
  <https://github.com/VertaAI/modeldb-client/pull/216>`_
- `implement verta.deployment.DeployedModel
  <https://github.com/VertaAI/modeldb-client/pull/221>`_

Bug Fixes
^^^^^^^^^
- `enable code version to be downloaded as a ZIP archive through the Web App
  <https://github.com/VertaAI/modeldb-client/pull/207>`_
- `fix bug in run.get_dataset_version()
  <https://github.com/VertaAI/modeldb-client/pull/223>`_
- `fix bug in dataset.get_latest_version()
  <https://github.com/VertaAI/modeldb-client/pull/227>`_
- `catch all unpickling-related errors in get_artifact()
  <https://github.com/VertaAI/modeldb-client/pull/213>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `keep cell execution numbers in example notebooks
  <https://github.com/VertaAI/modeldb-client/pull/217>`_


v0.13.6 (2019-09-05)
--------------------

Bug Fixes
^^^^^^^^^
- `fix small bugs in the _dataset submodule
  <https://github.com/VertaAI/modeldb-client/pull/211>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `update protos
  <https://github.com/VertaAI/modeldb-client/pull/212>`_


v0.13.5 (2019-09-05)
--------------------

Bug Fixes
^^^^^^^^^
- `fix various bugs in the _dataset submodule
  <https://github.com/VertaAI/modeldb-client/commit/971a8c6>`_


v0.13.3 (2019-09-04)
--------------------

Deprecations
^^^^^^^^^^^^
- `client.expt_runs, because its meaning is ambiguous; proj.expt_runs and expt.expt_runs are preferred
  <https://github.com/VertaAI/modeldb-client/pull/193>`_
- `ret_all_info parameter in querying methods, because it returns user-unfriendly objects
  <https://github.com/VertaAI/modeldb-client/pull/201>`_

New Features
^^^^^^^^^^^^
- `implement Client.set_experiment_run(id=…)
  <https://github.com/VertaAI/modeldb-client/pull/184>`_
- `implement dataset retrieval functions
  <https://github.com/VertaAI/modeldb-client/pull/205>`_
- `propagate error messages from the back end
  <https://github.com/VertaAI/modeldb-client/pull/196>`_

Bug Fixes
^^^^^^^^^
- `support run.get_*() when the value is None
  <https://github.com/VertaAI/modeldb-client/pull/191>`_
- `fix bug where Project, Experiment, and ExperimentRun objects couldn't be pickled
  <https://github.com/VertaAI/modeldb-client/pull/201>`_
- `fix bug when Datasets are created in Python 2
  <https://github.com/VertaAI/modeldb-client/pull/190>`_
- `log DatasetVersion timestamps as milliseconds, as expected by the Web App
  <https://github.com/VertaAI/modeldb-client/pull/182>`_
- `fix bug when the working directory is captured by run.log_modules()
  <https://github.com/VertaAI/modeldb-client/pull/187>`_
- `fix bug when run.log_modules() is used in Python 2
  <https://github.com/VertaAI/modeldb-client/pull/188>`_
- `fix bug when querying methods are called from an empty ExperimentRuns
  <https://github.com/VertaAI/modeldb-client/pull/195>`_
- `perform basic key validation in querying methods
  <https://github.com/VertaAI/modeldb-client/pull/194>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `create testing fixtures for deterministic input spaces
  <https://github.com/VertaAI/modeldb-client/pull/185>`_
- `fix data versioning tests
  <https://github.com/VertaAI/modeldb-client/pull/183>`_
- `fix non-artifact tests
  <https://github.com/VertaAI/modeldb-client/pull/186>`_
- `fix artifact tests
  <https://github.com/VertaAI/modeldb-client/pull/189>`_
- `implement model logging tests
  <https://github.com/VertaAI/modeldb-client/pull/192>`_
- `implement basic querying method tests
  <https://github.com/VertaAI/modeldb-client/pull/199>`_


v0.13.2 (2019-08-20)
--------------------

New Features
^^^^^^^^^^^^
- `add ExperimentRun.get_dataset_version()
  <https://github.com/VertaAI/modeldb-client/commit/f8831da>`_


v0.13.1 (2019-08-20)
--------------------

Bug Fixes
^^^^^^^^^
- `handle more states in DatasetVersion.__repr__()
  <https://github.com/VertaAI/modeldb-client/commit/801a3f3>`_


v0.13.0 (2019-08-20)
--------------------

New Features
^^^^^^^^^^^^
- `enable file extensions on artifacts in the Web App
  <https://github.com/VertaAI/modeldb-client/pull/144>`_
- `support basic data versioning
  <https://github.com/VertaAI/modeldb-client/compare/cfea45e...4bbfcd1>`_

Bug Fixes
^^^^^^^^^
- `convert everything to new-style classes for Python 2 compatibility
  <https://github.com/VertaAI/modeldb-client/pull/147/files>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `support dynamically fetching custom deployment URLs
  <https://github.com/VertaAI/modeldb-client/pull/145>`_
- `make Pillow an optional dependency
  <https://github.com/VertaAI/modeldb-client/pull/170>`_
- `support potentially handling a 401 on verifyConnection
  <https://github.com/VertaAI/modeldb-client/pull/152>`_


v0.12.9 (2019-08-13)
--------------------

New Features
^^^^^^^^^^^^
- `support passing in a full URL as the host parameter to Client()
  <https://github.com/VertaAI/modeldb-client/pull/166>`_

Bug Fixes
^^^^^^^^^
- `fix bugs regarding logging and retrieving datasets
  <https://github.com/VertaAI/modeldb-client/pull/167>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `propagate more deployment errors to the Client
  <https://github.com/VertaAI/modeldb-client/pull/165>`_


v0.12.8 (2019-08-08)
--------------------

Internal Changes
^^^^^^^^^^^^^^^^
- bump patch version to 8, to celebrate August 8th
- `handle getting Verta environment variables more consistently
  <https://github.com/VertaAI/modeldb-client/commit/ad99713>`_


v0.12.7 (2019-08-08)
--------------------

New Features
^^^^^^^^^^^^
- `support logging functions for deployment
  <https://github.com/VertaAI/modeldb-client/pull/157>`_
- `ignore virtual environment directories when logging custom modules for deployment
  <https://github.com/VertaAI/modeldb-client/pull/161>`_

Bug Fixes
^^^^^^^^^
- `define source code UTF-8 encoding for Python 2 compatibility
  <https://github.com/VertaAI/modeldb-client/pull/159>`_
- `use new-style classes for Python 2 compatibility
  <https://github.com/VertaAI/modeldb-client/commit/bbfa327>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `implement DeployedModel::from_url() factory method
  <https://github.com/VertaAI/modeldb-client/pull/163>`_
- `propagate runtime errors to the Client during DeployedModel.predict()
  <https://github.com/VertaAI/modeldb-client/commit/2f55d11>`_
- `add custom module logging example notebook
  <https://github.com/VertaAI/modeldb-client/pull/155>`_


v0.12.6 (2019-08-01)
--------------------

New Features
^^^^^^^^^^^^
- `implement a compress parameter on demo predict utility to enable request body compression
  <https://github.com/VertaAI/modeldb-client/pull/154>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `reduce redundancies in demo predict utility
  <https://github.com/VertaAI/modeldb-client/pull/153>`_


v0.12.5 (2019-07-26)
--------------------

New Features
^^^^^^^^^^^^
- `implement a debug parameter and attribute on Client to print verbose debugging information
  <https://github.com/VertaAI/modeldb-client/pull/149>`_


v0.12.4 (2019-07-25)
--------------------

New Features
^^^^^^^^^^^^
- `remove the need for log_modules()'s second argument (search_path)
  <https://github.com/VertaAI/modeldb-client/pull/148>`_


v0.12.3 (2019-07-17)
--------------------

Bug Fixes
^^^^^^^^^
- `ensure ModelAPI value names are cast to str
  <https://github.com/VertaAI/modeldb-client/commit/7cfb28e>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `identify model types by superclass
  <https://github.com/VertaAI/modeldb-client/commit/e3cc177>`_
- `update example notebooks with proper ModelAPI instantiation
  <https://github.com/VertaAI/modeldb-client/commit/fa868a1>`_
- `update demo notebook with log_code()
  <https://github.com/VertaAI/modeldb-client/commit/277f045>`_


v0.12.2 (2019-07-16)
--------------------

Bug Fixes
^^^^^^^^^
- `move Git repo check from Client init to log_code()
  <https://github.com/VertaAI/modeldb-client/commit/1fe9532>`_


v0.12.1 (2019-07-16)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `The non-public prediction utility now uses our updated REST prediction endpoint
  <https://github.com/VertaAI/modeldb-client/pull/128>`_

New Features
^^^^^^^^^^^^
- `implement log_code() and get_code() for code versioning
  <https://github.com/VertaAI/modeldb-client/pull/135>`_
- `allow periods in Artifact get functions
  <https://github.com/VertaAI/modeldb-client/pull/121>`_
- `enable retrieving integers as integers (instead of as floats) from the back end
  <https://github.com/VertaAI/modeldb-client/commit/cd34c94>`_

Bug Fixes
^^^^^^^^^
- `catch and raise duplicate column name error on ModelAPI initialization
  <https://github.com/VertaAI/modeldb-client/pull/123>`_
- `properly handle daylight saving time when logging observation timestamps
  <https://github.com/VertaAI/modeldb-client/pull/131>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `implement internal Configuration utility struct
  <https://github.com/VertaAI/modeldb-client/pull/134>`_
- `add PyTorch example notebook
  <https://github.com/VertaAI/modeldb-client/blob/master/workflows/examples/pytorch.ipynb>`_
- `implement internal utility for unwrapping directory paths into contained filepaths
  <https://github.com/VertaAI/modeldb-client/pull/124>`_
- `implement internal utilities for reading Git information from the local filesystem
  <https://github.com/VertaAI/modeldb-client/pull/126>`_
- `implement internal utilities for finding executing Python source files
  <https://github.com/VertaAI/modeldb-client/pull/133>`_
- `implement internal utility for getting the file extension from a filepath
  <https://github.com/VertaAI/modeldb-client/pull/129>`_
- `log file extensions with Artifacts
  <https://github.com/VertaAI/modeldb-client/pull/130>`_


v0.12.0 (2019-06-27)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `The dump() and load() functions have been removed from the public utils module.
  <https://github.com/VertaAI/modeldb-client/commit/c17013d>`_

New Features
^^^^^^^^^^^^
- `implement ignore_conn_err parameter and attribute to Client
  <https://github.com/VertaAI/modeldb-client/pull/118>`_
- `implement log_modules() for uploading custom Python modules for deployment
  <https://github.com/VertaAI/modeldb-client/pull/120>`_

Bug Fixes
^^^^^^^^^
- `enable logging lists, and dictionaries with string keys, as attributes on client.set_*() to match
  run.log_attribute()
  <https://github.com/VertaAI/modeldb-client/pull/113>`_
- `simplify stack traces by suppressing contexts during handling for a remaining handful of raise
  statements
  <https://github.com/VertaAI/modeldb-client/commit/886f3bb>`_
- `add missing error message to get_observation()
  <https://github.com/VertaAI/modeldb-client/commit/4c77343>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `use internal Connection utility object for connection configuration
  <https://github.com/VertaAI/modeldb-client/pull/118>`_
- `define Artifact Store bucket names using a checksum of the artifact
  <https://github.com/VertaAI/modeldb-client/pull/116>`_
- `check for dataset CSV existence before wget in census-end-to-end.ipynb
  <https://github.com/VertaAI/modeldb-client/commit/ccd7831>`_
- `expand and unify gitignores
  <https://github.com/VertaAI/modeldb-client/pull/119>`_


v0.11.7 (2019-06-10)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `The constructors for Project, Experiment, ExperimentRun, and ExperimentRuns—as well as with their
  _get() and _create() functions—now take an additional retry parameter, though these functions are
  all not intended for public use to begin with.
  <https://github.com/VertaAI/modeldb-client/pull/112>`_

New Features
^^^^^^^^^^^^
- `enable logging lists, and dictionaries with string keys, as attributes
  <https://github.com/VertaAI/modeldb-client/pull/109>`_
- `implement a max_retries parameter and attribute on Client to retry requests with exponential
  backoff on 403s, 503s, and 504s
  <https://github.com/VertaAI/modeldb-client/pull/112>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `delegate most REST calls to an internal utility function
  <https://github.com/VertaAI/modeldb-client/pull/112>`_
- `implement back end load test
  <https://github.com/VertaAI/modeldb-client/pull/110>`_
- `change Read the Docs sidebar from fixed to static
  <https://github.com/VertaAI/modeldb-client/commit/5f75fe6>`_
- `fix a bug that matplotlib has with macOS which was restricting testing
  <https://github.com/VertaAI/modeldb-client/commit/ddea440>`_


v0.11.6 (2019-06-07)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `Providing a cloudpickle version in the requirements for deployment that doesn't match the version
  used by the Client now raises an error instead of overwriting the line in the requirements.
  <https://github.com/VertaAI/modeldb-client/commit/871bef8>`_

New Features
^^^^^^^^^^^^
- `add ExperimentRun's Verta WebApp URL to its __repr__()
  <https://github.com/VertaAI/modeldb-client/pull/108>`_

Bug Fixes
^^^^^^^^^
- `use cloudpickle.__version__ instead of relying on pip
  <https://github.com/VertaAI/modeldb-client/commit/82c0f82>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `remove internal utility get_env_dependencies()
  <https://github.com/VertaAI/modeldb-client/commit/ce333bc>`_
- `update notebooks
  <https://github.com/VertaAI/modeldb-client/commit/0003f31>`_


v0.11.5 (2019-06-04)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `The dataset_csv parameter for log_model_for_deployment() has been replaced with two parameters
  for feature and target DataFrames.
  <https://github.com/VertaAI/modeldb-client/commit/4d11355>`_

Bug Fixes
^^^^^^^^^
- `properly render lists in docstrings
  <https://github.com/VertaAI/modeldb-client/commit/4f5c6c2>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `have the upload script clean out build directories after uploading
  <https://github.com/VertaAI/modeldb-client/commit/9d78662>`_


v0.11.4 (2019-05-31)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `The dataset_df parameter for log_model_for_deployment() has been renamed to dataset_csv.
  <https://github.com/VertaAI/modeldb-client/commit/ea49d06>`_

Bug Fixes
^^^^^^^^^
- `reset the correct streams in log_model_for_deployment() instead of model_api over and over again
  <https://github.com/VertaAI/modeldb-client/commit/d12fb6b>`_


v0.11.3 (2019-05-31)
--------------------

New Features
^^^^^^^^^^^^
- `implement __version__ attribute on package
  <https://github.com/VertaAI/modeldb-client/commit/31aee4b>`_

Bug Fixes
^^^^^^^^^
- `remove unsupported dependency on pandas and NumPy in utils module
  <https://github.com/VertaAI/modeldb-client/commit/659ceca>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `move package version string from verta/setup.py to verta/verta/__about__.py
  <https://github.com/VertaAI/modeldb-client/commit/31aee4b>`_
- `remove old model API tests that have been superseded by property-based tests
  <https://github.com/VertaAI/modeldb-client/commit/4a0c799>`_
- `add pandas as a testing dependency
  <https://github.com/VertaAI/modeldb-client/commit/cc47d85>`_


v0.11.2 (2019-05-30)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `Parameters for Client.set_* functions have been renamed to name and id, from e.g. proj_name and
  _proj_id.
  <https://github.com/VertaAI/modeldb-client/commit/889130d>`_
- `The _id attribute of Project, Experiment, and ExperimentRun have been renamed to id.
  <https://github.com/VertaAI/modeldb-client/commit/eb832fb>`_
- `The default generated names for Project, Experiment, and ExperimentRun have been shortened.
  <https://github.com/VertaAI/modeldb-client/commit/3e515ab>`_

Bug Fixes
^^^^^^^^^
- `fix typos in Client.set_* error messages
  <https://github.com/VertaAI/modeldb-client/commit/0b8e4f9>`_


v0.11.1 (2019-05-29)
--------------------

Bug Fixes
^^^^^^^^^
- `fix internal utility get_env_dependencies() for compatibility with Python 3.6 and earlier
  <https://github.com/VertaAI/modeldb-client/commit/03b4005>`_


v0.11.0 (2019-05-29)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `log_model_for_deployment() now no longer requires a dataset argument, but requires a model API
  argument. The order of parameters has changed, and dataset_csv has been renamed to dataset_df.
  <https://github.com/VertaAI/modeldb-client/pull/99>`_

New Features
^^^^^^^^^^^^
- `implement ModelAPI utility class for generating model APIs
  <https://github.com/VertaAI/modeldb-client/pull/102>`_

Internal Changes
^^^^^^^^^^^^^^^^
- `create an example notebook that downloads our beloved Census data with wget
  <https://github.com/VertaAI/modeldb-client/blob/b998b6b/workflows/examples-without-verta/notebooks/sklearn-census.ipynb>`_
- `rename the "scikit" model type to "sklearn"
  <https://github.com/VertaAI/modeldb-client/pull/102>`_
- `delete old internal model API generation utility
  <https://github.com/VertaAI/modeldb-client/pull/102>`_
- `update demo utility predict function to simply dump the JSON input into the request body
  <https://github.com/VertaAI/modeldb-client/commit/094494d#diff-5ecfc26>`_
- `implement internal utility to check for exact version pins in a requirements.txt
  <https://github.com/VertaAI/modeldb-client/pull/100>`_
- `implement internal utility to obtain the local environment's Python version number
  <https://github.com/VertaAI/modeldb-client/pull/98>`_
- `update READMEs
  <https://github.com/VertaAI/modeldb-client/commit/f0579f2>`_
- `add utils module to API reference
  <https://github.com/VertaAI/modeldb-client/commit/f83a203>`_
- `implement tests for model API generation
  <https://github.com/VertaAI/modeldb-client/commit/5982221>`_
- `implement property-based tests for model API generation
  <https://github.com/VertaAI/modeldb-client/commit/d3e2a58>`_
- `add deepdiff to testing requirements
  <https://github.com/VertaAI/modeldb-client/commit/4edf10b>`_
- `add hypothesis to testing requirements
  <https://github.com/VertaAI/modeldb-client/commit/8044b6a>`_


v0.10.2 (2019-05-22)
--------------------
no functional changes


v0.10.1 (2019-05-22)
--------------------

Bug Fixes
^^^^^^^^^
- `properly expose intermediate subpackages for compatibility with Python 3.2 and earlier
  <https://github.com/VertaAI/modeldb-client/commit/d3037ac>`_


v0.10.0 (2019-05-16)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `log_hyperparameters() now must take a single, whole dictionary as an argument and no longer accepts
  dictionary unpacking.
  <https://github.com/VertaAI/modeldb-client/pull/96>`_
- `Getting observations from an ExperimentRun now returns tuples pairing observations with their
  timestamps.
  <https://github.com/VertaAI/modeldb-client/pull/83>`_
- `Passing a string into artifact logging functions now attempts to open a file located at the path
  represented by that string, rather than simply logging the string itself.
  <https://github.com/VertaAI/modeldb-client/pull/94>`_
- `Attempting to log an unsupported datatype now throws a TypeError instead of a ValueError.
  <https://github.com/VertaAI/modeldb-client/pull/90/files>`_
- `Logging artifacts now uses cloudpickle by default, instead of pickle.
  <https://github.com/VertaAI/modeldb-client/pull/90/files>`_
- `The internal logic for getting a Project by name has changed, and will be incompatible with old
  versions of the Verta Back End.
  <https://github.com/VertaAI/modeldb-client/commit/595b707>`_
- `The internal logic for handling uploading custom models for deployment has changed, and will be
  incompatible with old versions of the Verta Back End.
  <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `The internal logic for getting an ExperimentRun by name has changed, and may be incompatible with
  old versions of the Verta Back End.
  <https://github.com/VertaAI/modeldb-client/pull/89>`_

New Features
^^^^^^^^^^^^
- `associate user-specified or automatically-generated timestamps with observations
  <https://github.com/VertaAI/modeldb-client/pull/83>`_
- `implement methods on ExperimentRun for logging and getting tags
  <https://github.com/VertaAI/modeldb-client/pull/84/files>`_
- `implement methods on ExperimentRun for logging multiple attributes, metrics, or hyperparameters
  in a single transaction
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
- `implement a secondary predict function in demo utilities that returns the raw HTML response instead
  of a formatted response
  <https://github.com/VertaAI/modeldb-client/pull/92>`_
- `move our example notebooks from workflows/demos/ to workflows/examples/
  <https://github.com/VertaAI/modeldb-client/commit/de197f6>`_
- `change "unknown" model type to "custom" in model API
  <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `add "keras" deserialization in model API
  <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `add cloudpickle to requirements with the locally pinned version if it was used when logging for
  deployment
  <https://github.com/VertaAI/modeldb-client/pull/95>`_
- `implement handful of small fixes to maintain Python 2.7 compatibility
  <https://github.com/VertaAI/modeldb-client/pull/97>`_
