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

        self._status_url = "https://{}/api/v1/deployment/status/{}".format(socket, model_id)

        self._token = None
        self._url = None
        self._headers = None

    def __repr__(self):
        return "<Model {}>".format(self._id)

    def _set_token_and_url(self):
        response = requests.get(self._status_url)
        response.raise_for_status()
        status = response.json()
        if 'token' in status and 'api' in status:
            self._token = status['token']
            self._url = "https://{}{}".format(self._socket, status['api'])
        else:
            raise RuntimeError("deployment is not ready")

    def _set_headers(self, key="model_api.json"):
        # get url to get model_api.json from artifact store
        params = {'id': self._id, 'key': key, 'method': "GET"}
        response = requests.post("https://{}/v1/experiment-run/getUrlForArtifact".format(self._socket),
                                 json=params, headers=self._auth)
        response.raise_for_status()

        # get model_api.json
        get_artifact_url = response.json()['url']
        response = requests.get(get_artifact_url)
        response.raise_for_status()
        model_api = json.loads(response.content)

        model_api_input = model_api['input']

        if 'fields' not in model_api_input:
            self._headers = model_api_input['name']
        else:
            self._headers = [field['name'] for field in model_api_input['fields']]

    def _predict(self, x, return_input_body=False):
        """This is like ``DeployedModel.predict()``, but returns the raw ``Response`` for debugging."""
        if self._token is None or self._url is None:
            self._set_token_and_url()
        if self._headers is None:
            self._set_headers()

        result = requests.post(self._url,
                               headers={
                                   'Access-token': self._token,
                                   'Content-length': str(len(json.dumps(x).encode('utf-8'))),
                               },
                               json=x)

        if return_input_body:
            return result, input_body
        else:
            return result

    @property
    def is_deployed(self):
        response = requests.get(self._status_url)
        return response.ok and 'token' in response.json()

    def predict(self, x):
        """
        Make a prediction using input `x`.

        This function fetches the model api artifact (using key "model_api.json") to wrap `x` before
        sending it to the deployed model for a prediction.

        Parameters
        ----------
        x : list
            List of Sequence of feature values representing a single data point.

        Returns
        -------
        prediction : dict or None
            Output returned by the deployed model for `x`. If the prediction request returns an
            error, None is returned instead as a silent failure.

        """
        response = self._predict(x)

        if not response.ok:
            self._set_token_and_url()  # try refetching prediction token and URL
            response = self._predict(x)
            if not response.ok:
                self._set_headers()  # try refetching input headers
                response = self._predict(x)
                if not response.ok:
                    return "model is warming up; please wait"
        return response.json()
