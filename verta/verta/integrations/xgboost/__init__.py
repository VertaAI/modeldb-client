# -*- coding: utf-8 -*-

from ... import _six

import xgboost as xgb

from ... import _utils


def verta_callback(run):
    """
    XGBoost callback that automates logging to Verta during booster training.

    This callback logs ``eval_metric``\ s passed into ``xgb.train()``.

    .. versionadded:: 0.13.20

    Parameters
    ----------
    run : :class:`~verta.client.ExperimentRun`
        Experiment Run tracking this model.

    Examples
    --------
    >>> from verta.integrations.xgboost import verta_callback
    >>> run = client.set_experiment_run()
    >>> run.log_hyperparameters(params)
    >>> bst = xgb.train(
    ...     params, dtrain,
    ...     evals=[(dtrain, "train")],
    ...     callbacks=[verta_callback(run)],
    ... )

    """
    def callback(env):
        for metric, val in env.evaluation_result_list:
            run.log_observation(metric, val)
        # TODO: support `xgb.cv()`, which gives `(metric, val, std_dev)` across folds
    return callback
