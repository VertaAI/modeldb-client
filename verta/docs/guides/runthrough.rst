60-Second Runthrough
====================

1. Install the **Verta** Python package.

  .. code-block:: console

    $ pip install verta

  Verta currently officially supports Python 2.7 & 3.5–3.7. For more information, read the
  `installation guide <installation.html>`_.

2. Integrate the Verta package into your workflow.

  a. Connect to the Verta back end:

    .. code-block:: python

        from verta import Client
        client = Client(host, email, dev_key)

    For more information, read `our platform documentation <https://verta.readme.io/docs>`_.

  b. Log things that matter to you:

    .. code-block:: python

        proj = client.set_project("Fraud Detection")
        expt = client.set_experiment("Recurrent Neural Net")

    .. code-block:: python

        run = client.set_experiment_run("Two-Layer Dropout LSTM")
        ...
        run.log_hyperparameter("num_layers", 2)
        run.log_hyperparameter("hidden_size", 512)
        run.log_hyperparameter("dropout", 0.5)
        run.log_metric("accuracy", 0.95)

    For more information, read the `workflow guide <workflow.html>`_ and the `API reference
    <../reference/api.html>`_.

3. Now that we've logged a few runs, head to the `Verta Web App <https://app.verta.ai>`_ to view them!
