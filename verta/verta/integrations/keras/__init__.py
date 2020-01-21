# -*- coding: utf-8 -*-

from ... import _six

# TODO: use `keras` module imported in calling scope
try:
    from tensorflow import keras
except ImportError:  # TensorFlow not installed
    import keras

from ... import _utils


class VertaCallback(keras.callbacks.Callback):
    """
    Keras callback that automates logging to Verta during model training.

    .. versionadded:: 0.13.20

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
            self.run.log_hyperparameter("optimizer", model.optimizer._name)
        except:
            pass  # don't halt execution

        try:
            if isinstance(model.loss, _six.string_types):
                self.run.log_hyperparameter("loss", model.loss)
            elif isinstance(model.loss, keras.losses.Loss):
                self.run.log_hyperparameter("loss", model.loss.__class__.__name__)
            else:  # function from `keras.losses`
                self.run.log_hyperparameter("loss", model.loss.__name__)
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

    # TODO: log metrics on_(train|test|predict)_end
    # TODO: log model checkpoints as artifacts
