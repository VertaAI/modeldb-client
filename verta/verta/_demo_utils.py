# -*- coding: utf-8 -*-

import warnings

from .deployment import DeployedModel as TrueDeployedModel


class DeployedModel(TrueDeployedModel):
    def __init__(self, socket, model_id):
        warnings.warn("`DeployedModel` is being moved to the `verta.deployment` module,"
                      " and `verta._demo_utils` will be removed in a future version;"
                      " please refer to the Verta documentation for usage notes",
                      category=FutureWarning)
        super(DeployedModel, self).__init__(run_id=model_id, host=socket)
