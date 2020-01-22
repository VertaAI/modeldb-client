# -*- coding: utf-8 -*-

from ... import _six

import tensorflow as tf
from tensorflow.compat.v1 import summary  # pylint: disable=import-error
from tensorflow.compat.v1.train import SessionRunArgs  # pylint: disable=import-error
try:
    from tensorflow.estimator import SessionRunHook
except ImportError:  # tensorflow<2.0
    from tf.train import SessionRunHook

from ... import _utils


def _parse_summary_proto_str(proto_str):
    """
    Converts the serialized protobuf `SessionRunValues.results['summary']` into a `Message` object.

    """
    summary_msg = summary.Summary()
    summary_msg.ParseFromString(proto_str)
    return summary_msg


class VertaHook(SessionRunHook):
    """
    TensorFlow Estimator callback that automates logging to Verta during model training.

    .. versionadded:: 0.13.20

    Parameters
    ----------
    run : :class:`~verta.client.ExperimentRun`
        Experiment Run tracking this model.
    every_n_steps : int, default 1000
        How often to log summary metrics.

    Examples
    --------
    >>> from verta.integrations.tensorflow import VertaHook
    >>> run = client.set_experiment_run()
    >>> estimator.train(
    ...     input_fn=train_input_fn,
    ...     hooks=[VertaHook(run)],
    ... )

    """
    def __init__(self, run, every_n_steps=1000):
        self._summary = None
        self._every_n_steps = every_n_steps
        self._step = 0

        self.run = run

    def begin(self):
        if self._summary is None:
            self._summary = summary.merge_all()

    def before_run(self, run_context):
        self._step += 1
        return SessionRunArgs({"summary": self._summary})

    def after_run(self, run_context, run_values):
        if self._step % self._every_n_steps != 0:
            return

        summary_msg = _parse_summary_proto_str(run_values.results['summary'])

        for value in summary_msg.value:
            if value.WhichOneof("value") == "simple_value":
                try:
                    self.run.log_observation(value.tag, value.simple_value)
                except:
                    pass  # don't halt execution
            # TODO: support other value types
