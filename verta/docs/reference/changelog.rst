Release Notes
=============

v0.11.0 (2019-05-29)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^

v0.10.2 (2019-05-22)
--------------------
no functional changes


v0.10.1 (2019-05-22)
--------------------

Bug Fixes
^^^^^^^^^
- `properly expose intermediate subpackages for compatibility with Python 3.2 and earlier <https://github.com/VertaAI/modeldb-client/commit/d3037ac5670c022c2f2aa4b1f50b49e9c19646b0>`_


v0.10.0 (2019-05-16)
--------------------

Backwards Incompatibilities
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- `log_hyperparameters() now must take a single, whole dictionary as an argument and no longer accepts dictionary
  unpacking. <https://github.com/VertaAI/modeldb-client/pull/96>`_
- `Getting observations from an ExperimentRun now returns tuples pairing observations with their timestamps.
  <https://github.com/VertaAI/modeldb-client/pull/83>`_
- `Passing a string into artifact logging functions now attempts to open a file located at the path represented by that
  string, rather than simply logging the string itself. <https://github.com/VertaAI/modeldb-client/pull/94>`_
- `Attempting to log an unsupported datatype now throws a TypeError instead of a ValueError. <https://github.com/VertaAI/modeldb-client/pull/90/files>`_
- `Logging artifacts now uses cloudpickle by default, instead of pickle. <https://github.com/VertaAI/modeldb-client/pull/90/files>`_
- `The internal logic for getting a Project by name has changed, and will be incompatible with old versions of the Verta
  Back End. <https://github.com/VertaAI/modeldb-client/commit/595b70749b585f13a38afef6b91b4aeae633c5ae>`_
- `The internal logic for handling uploading custom models for deployment has changed, and will be incompatible with old
  versions of the Verta Back End. <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `The internal logic for getting an ExperimentRun by name has changed, and may be incompatible with old versions of the
  Verta Back End. <https://github.com/VertaAI/modeldb-client/pull/89>`_



New Features
^^^^^^^^^^^^
- `associate user-specified or automatically-generated timestamps with observations <https://github.com/VertaAI/modeldb-client/pull/83>`_
- `implement methods on ExperimentRun for logging and getting tags <https://github.com/VertaAI/modeldb-client/pull/84/files>`_
- `implement methods on ExperimentRun for logging multiple attributes, metrics, or hyperparameters in a single transaction
  <https://github.com/VertaAI/modeldb-client/pull/87>`_
- `enable uploading custom model APIs for deployment <https://github.com/VertaAI/modeldb-client/pull/91>`_
- `create functions specifically for logging artifact paths without attempting uploads <https://github.com/VertaAI/modeldb-client/pull/94>`_


Bug Fixes
^^^^^^^^^
- `reset stream pointer on failed deserialization attempts <https://github.com/VertaAI/modeldb-client/pull/86>`_


Internal Changes
^^^^^^^^^^^^^^^^
- `convert pandas DataFrames into CSVs when logging for deployment for data monitoring <https://github.com/VertaAI/modeldb-client/pull/85>`_
- `implement a secondary predict function in demo utilities that returns the raw HTML response instead of a formatted response
  <https://github.com/VertaAI/modeldb-client/pull/92>`_
- `move our example notebooks from workflows/demos/ to workflows/examples/ <https://github.com/VertaAI/modeldb-client/commit/de197f6821ccbb904a4cd1e45b66b45e5c7f68a6>`_
- `change "unknown" model type to "custom" in model API <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `add "keras" deserialization in model API <https://github.com/VertaAI/modeldb-client/pull/93>`_
- `add cloudpickle to requirements with the locally pinned version if it was used when logging for deployment <https://github.com/VertaAI/modeldb-client/pull/95>`_
- `implement handful of small fixes to maintain Python 2.7 compatibility <https://github.com/VertaAI/modeldb-client/pull/97>`_
