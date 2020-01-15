# -*- coding: utf-8 -*-

from __future__ import print_function

from . import _six

import os

import requests

from . import _utils
from . import utils


try:
    import tensorflow
except ImportError:  # TensorFlow not installed
    tensorflow = None


if tensorflow is not None:
    class KerasCallback(tensorflow.keras.callbacks.Callback):
        """


        Parameters
        ----------
        run : :class:`~verta.client.ExperimentRun`
            Experiment Run tracking this model.

        Examples
        --------
        >>> run = client.set_experiment_run()
        >>> model.fit(
        ...     X_train, y_train,
        ...     callbacks=[verta.integrations.KerasCallback(run)],
        ... )

        """
        def __init__(self, run):
            self.run = run

        def on_epoch_end(self, epoch, logs=None):
            if logs is not None:
                for key, val in _six.viewitems(logs):
                    self.run.log_observation(key, float(val))
