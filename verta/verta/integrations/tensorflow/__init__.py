# -*- coding: utf-8 -*-

from ... import _six

import tensorflow as tf

from ... import _utils


# `SessionRunHook` moved to `tf.estimator` in v2.0
SessionRunHook = getattr(tf.estimator, 'SessionRunHook', tf.train.SessionRunHook)


class VertaHook(SessionRunHook):
    def __init__(self):
        pass

    def after_create_session(self, session, coord):
        pass

    def before_run(self, run_context):
        pass

    def after_run(self, run_context, run_values):
        pass

    def end(self, session):
        pass
