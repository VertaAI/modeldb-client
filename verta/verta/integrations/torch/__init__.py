# -*- coding: utf-8 -*-

from ... import _six

import torch

from ... import _utils


def verta_hook(run):
    """
    PyTorch module hook that automates logging to Verta during training.

    .. versionadded:: 0.13.20

    Parameters
    ----------
    run : :class:`~verta.client.ExperimentRun`
        Experiment Run tracking this model.

    Examples
    --------
    >>> from verta.integrations.torch import verta_hook
    >>> run = client.set_experiment_run()
    >>> model.register_forward_hook(verta_hook(run))
    >>> output = model(X_train)

    """
    def hook(module, input, output):
        for i, layer in enumerate(module.children()):
            try:
                run.log_hyperparameter("layer_{}_name".format(i), layer.__class__.__name__)
            except:
                pass  # don't halt execution

            layer_params = {
                "layer_{}_{}".format(i, attr): getattr(layer, attr)
                for attr in layer.__dict__
                if not attr.startswith('_')
                and attr != "training"
            }
            try:
                run.log_hyperparameters(layer_params)
            except:
                pass  # don't halt execution

            print(output)
    return hook
