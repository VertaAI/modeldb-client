# -*- coding: utf-8 -*-

import warnings

from .deployment import DeployedModel as TrueDeployedModel


class DeployedModel(TrueDeployedModel):
    def __init__(self, socket, model_id):
        warnings.warn("`DeployedModel` is being moved to the `verta.deployment` module,"
                      " and `verta._demo_utils` will be removed in a future version;"
                      " please refer to the Verta documentation for usage notes",
                      category=FutureWarning)
        self.__dict__ = super(DeployedModel, self).from_id(run_id=model_id, host=socket).__dict__
