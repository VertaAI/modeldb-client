ExperimentRun
=============

.. currentmodule:: verta.client

.. autoclass:: ExperimentRun

Basic Metadata
--------------

Attributes
^^^^^^^^^^
Attributes are descriptive metadata, such as the team responsible for this model or the expected training time.

.. automethod:: ExperimentRun.log_attribute
.. automethod:: ExperimentRun.log_attributes
.. automethod:: ExperimentRun.get_attribute
.. automethod:: ExperimentRun.get_attributes

Hyperparameters
^^^^^^^^^^^^^^^
Hyperparameters are model configuration metadata, such as the loss function or the regularization penalty.

.. automethod:: ExperimentRun.log_hyperparameter
.. automethod:: ExperimentRun.log_hyperparameters
.. automethod:: ExperimentRun.get_hyperparameter
.. automethod:: ExperimentRun.get_hyperparameters

Metrics
^^^^^^^
Metrics are unique performance metadata, such as accuracy or loss on the full training set.

.. automethod:: ExperimentRun.log_metric
.. automethod:: ExperimentRun.log_metrics
.. automethod:: ExperimentRun.get_metric
.. automethod:: ExperimentRun.get_metrics

Observations
^^^^^^^^^^^^
Observations are recurring metadata that are repeatedly measured over time, such as batch losses over an epoch or memory
usage.

.. automethod:: ExperimentRun.log_observation
.. automethod:: ExperimentRun.get_observation
.. automethod:: ExperimentRun.get_observations

Tags
^^^^
Tags are short textual labels used to help identify a run, such as its purpose or its environment.

.. automethod:: ExperimentRun.log_tag
.. automethod:: ExperimentRun.log_tags
.. automethod:: ExperimentRun.get_tags

Artifacts
---------

Artifacts
^^^^^^^^^
.. automethod:: ExperimentRun.log_artifact
.. automethod:: ExperimentRun.log_artifact_path
.. automethod:: ExperimentRun.get_artifact

Datasets
^^^^^^^^
.. automethod:: ExperimentRun.log_dataset
.. automethod:: ExperimentRun.log_dataset_path
.. automethod:: ExperimentRun.get_dataset

Images
^^^^^^
.. automethod:: ExperimentRun.log_image
.. automethod:: ExperimentRun.log_image_path
.. automethod:: ExperimentRun.get_image

Models
^^^^^^
.. automethod:: ExperimentRun.log_model
.. automethod:: ExperimentRun.log_model_path
.. automethod:: ExperimentRun.get_model

Advanced Uses
-------------

Code Versioning
^^^^^^^^^^^^^^^
.. automethod:: ExperimentRun.log_code
.. automethod:: ExperimentRun.get_code

Deployment
^^^^^^^^^^
.. automethod:: ExperimentRun.log_model_for_deployment
.. automethod:: ExperimentRun.log_modules
