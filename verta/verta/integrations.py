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

        """
        def __init__(self, run):
            self.run = run

        def on_epoch_end(self, epoch, logs={}):
            for key, val in _six.viewitems(logs):
                self.run.log_observation(key, float(val))
