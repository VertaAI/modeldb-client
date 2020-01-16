# -*- coding: utf-8 -*-

from __future__ import print_function

from ... import _six

import os

import requests

from ... import _utils


try:
    from tensorflow import keras
except ImportError:  # TensorFlow not installed
    import keras


class VertaCallback(keras.callbacks.Callback):
    """
    Keras callback that automates logging to Verta during model operation.

    Parameters
    ----------
    run : :class:`~verta.client.ExperimentRun`
        Experiment Run tracking this model.

    Examples
    --------
    >>> from verta.integrations.keras import VertaCallback
    >>> run = client.set_experiment_run()
    >>> model.compile(
    ...     loss="categorical_crossentropy",
    ...     optimizer="adam",
    ...     metrics=["accuracy"],
    ... )
    >>> model.fit(
    ...     X_train, y_train,
    ...     callbacks=[VertaCallback(run)],
    ... )

    """
    def __init__(self, run):
        self.run = run

    def set_params(self, params):
        if isinstance(params, dict):
            for key, val in _six.viewitems(params):
                try:
                    self.run.log_hyperparameter(key, _utils.to_builtin(val))
                except:
                    pass  # don't halt execution

    def set_model(self, model):
        try:
            optimizer = model.optimizer._name
            self.run.log_hyperparameter("optimizer", optimizer)
        except:
            pass  # don't halt execution

        try:
            loss = model.loss
            self.run.log_hyperparameter("loss", _utils.to_builtin(loss))
        except:
            pass  # don't halt execution

        for i, layer in enumerate(model.layers):
            try:
                self.run.log_hyperparameter("layer_{}_name".format(i), layer._name)
            except:
                pass  # don't halt execution

            try:
                self.run.log_hyperparameter("layer_{}_size".format(i), layer.units)
            except:
                pass  # don't halt execution

            try:
                self.run.log_hyperparameter("layer_{}_activation".format(i), layer.activation.__name__)
            except:
                pass  # don't halt execution

            try:
                self.run.log_hyperparameter("layer_{}_dropoutrate".format(i), layer.rate)
            except:
                pass  # don't halt execution

    def on_epoch_end(self, epoch, logs=None):
        if isinstance(logs, dict):
            for key, val in _six.viewitems(logs):
                try:
                    self.run.log_observation(key, _utils.to_builtin(val))
                except:
                    pass  # don't halt execution
