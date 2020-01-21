# -*- coding: utf-8 -*-

from ... import _six

import tensorflow as tf

from ... import _utils


# `SessionRunHook` moved to `tf.estimator` in v2.0
if hasattr(tf.estimator, 'SessionRunHook'):
    SessionRunHook = tf.estimator.SessionRunHook
else:
    SessionRunHook = tf.train.SessionRunHook


class _VertaHook(SessionRunHook):
    """
    TensorFlow Estimator callback that automates logging to Verta during model training.

    .. versionadded:: 0.13.20

    Parameters
    ----------
    run : :class:`~verta.client.ExperimentRun`
        Experiment Run tracking this model.

    Examples
    --------
    >>> from verta.integrations.tensorflow import VertaHook
    >>> run = client.set_experiment_run()
    >>> estimator.train(
    ...     input_fn=train_input_fn,
    ...     hooks=[VertaHook(run)],
    ... )

    """
    def __init__(self, run):
        self.run = run

    def begin(self):
        pass

    def before_run(self, run_context):
        print("RUN CONTEXT:")
        print(run_context)

    def after_run(self, run_context, run_values):
        print("RUN CONTEXT:")
        print(run_context)
        print("RUN VALUES:")
        print(run_values)

    def end(self, session):
        pass
