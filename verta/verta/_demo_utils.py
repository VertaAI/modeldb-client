import six
from six.moves.urllib.parse import urlparse

import json
import os

import requests


class DeployedModel:
    """
    Object for interacting with deployed models.

    This class provides functionality for sending predictions to a deployed model on the Verta
    backend.

    Authentication credentials must be present in the environment through `$VERTA_EMAIL` and
    `$VERTA_DEV_KEY`.

    Parameters
    ----------
    socket : str
        Hostname of the node running the Verta backend.
    model_id : str
        id of the deployed ExperimentRun/ModelRecord.

    Attributes
    ----------
    is_deployed : bool
        Whether this model is currently deployed.

    """
    _GRPC_PREFIX = "Grpc-Metadata-"

    def __init__(self, socket, model_id):
        socket = urlparse(socket)
        socket = socket.path if socket.netloc == '' else socket.netloc

        self._socket = socket
        self._auth = {self._GRPC_PREFIX+'email': os.environ['VERTA_EMAIL'],
                      self._GRPC_PREFIX+'developer_key': os.environ['VERTA_DEV_KEY'],
                      self._GRPC_PREFIX+'source': "PythonClient"}
        self._id = model_id

        self._prediction_token = None
        self._input_headers = None

    def __repr__(self):
        return "<Model {}>".format(self._id)

    def _set_prediction_token(self):
        status_url = "https://{}/api/v1/deployment/status/{}".format(self._socket, self._id)
        response = requests.get(status_url)
        response.raise_for_status()
        status = response.json()
        try:
            self._prediction_token = status['token']
        except KeyError:
            six.raise_from(RuntimeError("deployment is not ready"), None)

    def _set_input_headers(self, key="model_api.json"):
        # get url to get model_api.json from artifact store
        get_url_url = "https://{}/v1/experiment-run/getUrlForArtifact".format(self._socket)
        params = {'id': self._id, 'key': key, 'method': "GET"}
        response = requests.post(get_url_url, json=params, headers=self._auth)
        response.raise_for_status()

        # get model_api.json
        get_artifact_url = response.json()['url']
        response = requests.get(get_artifact_url)
        response.raise_for_status()
        model_api = json.loads(response.content)

        self._input_headers = [field['name'] for field in model_api['input']['fields']]

    @property
    def is_deployed(self):
        status_url = "https://{}/api/v1/deployment/status/{}".format(self._socket, self._id)
        response = requests.get(status_url)
        return response.ok and 'token' in response.json()

    def predict(self, x):
        """
        Make a prediction using input `x`.

        This function fetches the model api artifact (using key "model_api.json") to wrap `x` before
        sending it to the deployed model for a prediction.

        Parameters
        ----------
        x : list-like
            Sequence of feature values representing a single data point.

        Returns
        -------
        prediction : dict or None
            Output returned by the deployed model for `x`. If the prediction request returns an
            error, None is returned instead as a silent failure.

        """
        if self._prediction_token is None:
            self._set_prediction_token()
        if self._input_headers is None:
            self._set_input_headers()
        
        prediction_url = "https://{}/api/v1/predict/{}".format(self._socket, self._id)
        input_data = dict(zip(self._input_headers, x))
        input_request = {'token': self._prediction_token,
                         'data': json.dumps(input_data)}
        response = requests.post(prediction_url, data=input_request)
        if not response.ok:
            self._set_prediction_token()  # try refetching token
            response = requests.post(prediction_url, data=input_request)
            if not response.ok:
                self._set_input_headers()  # try refetching input headers
                response = requests.post(prediction_url, data=input_request)
                if not response.ok:
                    return None  # silence error for now
        return response.json()
    