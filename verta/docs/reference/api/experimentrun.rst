ExperimentRun
=============

.. currentmodule:: verta.client

.. autoclass:: ExperimentRun

Basic Metadata
--------------

Attributes
^^^^^^^^^^
|attributes description|

.. automethod:: ExperimentRun.log_attribute
.. automethod:: ExperimentRun.log_attributes
.. automethod:: ExperimentRun.get_attribute
.. automethod:: ExperimentRun.get_attributes

Hyperparameters
^^^^^^^^^^^^^^^
|hyperparameters description|

.. automethod:: ExperimentRun.log_hyperparameter
.. automethod:: ExperimentRun.log_hyperparameters
.. automethod:: ExperimentRun.get_hyperparameter
.. automethod:: ExperimentRun.get_hyperparameters

Metrics
^^^^^^^
|metrics description|

.. automethod:: ExperimentRun.log_metric
.. automethod:: ExperimentRun.log_metrics
.. automethod:: ExperimentRun.get_metric
.. automethod:: ExperimentRun.get_metrics

Observations
^^^^^^^^^^^^
|observations description|

.. automethod:: ExperimentRun.log_observation
.. automethod:: ExperimentRun.get_observation
.. automethod:: ExperimentRun.get_observations

Tags
^^^^
|tags description|

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
