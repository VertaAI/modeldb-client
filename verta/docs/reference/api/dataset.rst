Data Versioning
===============


Creation and Logging
^^^^^^^^^^^^^^^^^^^^

.. automethod:: verta.client.Client.set_dataset
.. automethod:: verta.client.ExperimentRun.log_dataset_version
    :noindex:
.. automethod:: verta.client.ExperimentRun.get_dataset_version
    :noindex:


Object APIs
^^^^^^^^^^^

.. automodule:: verta._dataset
    :members:
.. automethod:: verta._dataset.LocalDataset.create_version
    :noindex:
.. automethod:: verta._dataset.S3Dataset.create_version
    :noindex:
.. automethod:: verta._dataset.AtlasHiveDataset.create_version
    :noindex:
.. automethod:: verta._dataset.BigQueryDataset.create_version
    :noindex:
