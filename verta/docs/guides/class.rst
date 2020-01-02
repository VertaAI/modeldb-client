Class Models
============

But what if the model you have is not directly serializable?
What if its configuration is tied to your system hardware
TensorFlow ``Session``

.. code-block:: python

    class Model(object):
        def __init__(self, artifacts):
            pass

        def predict(self, data):
            pass

.. code-block:: python

    run.log_artifact("weights", "model/weights.json")

.. code-block:: python

    run.log_model(Model, artifacts=["weights"])
    run.log_requirements(["tensorflow"])

.. code-block:: python

    artifacts = run.fetch_artifacts(["weights"])
