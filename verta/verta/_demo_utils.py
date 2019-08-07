import six
from six.moves.urllib.parse import urlparse

import json
import gzip
import os
import time

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
        self._id = model_id

        self._status_url = "https://{}/api/v1/deployment/status/{}".format(socket, model_id)

        self._url = None

        self._session = requests.Session()

    def __repr__(self):
        return "<Model {}>".format(self._id)

    def _set_token_and_url(self):
        response = self._session.get(self._status_url)
        response.raise_for_status()
        status = response.json()
        if 'token' in status and 'api' in status:
            self._session.headers['Access-token'] = status['token']
            self._url = "https://{}{}".format(self._socket, status['api'])
        else:
            raise RuntimeError("token not found in status endpoint response; deployment may not be ready")

    def _predict(self, x, compress=False):
        """This is like ``DeployedModel.predict()``, but returns the raw ``Response`` for debugging."""
        if 'Access-token' not in self._session.headers or self._url is None:
            self._set_token_and_url()

        if compress:
            # create gzip
            gzstream = six.BytesIO()
            with gzip.GzipFile(fileobj=gzstream, mode='wb') as gzf:
                gzf.write(six.ensure_binary(json.dumps(x)))
            gzstream.seek(0)

            return self._session.post(
                self._url,
                headers={'Content-Encoding': 'gzip'},
                data=gzstream.read(),
            )
        else:
            return self._session.post(self._url, json=x)

    @property
    def is_deployed(self):
        response = self._session.get(self._status_url)
        return response.ok and 'token' in response.json()

    def predict(self, x, compress=False, max_retries=5):
        """
        Make a prediction using input `x`.

        This function fetches the model api artifact (using key "model_api.json") to wrap `x` before
        sending it to the deployed model for a prediction.

        Parameters
        ----------
        x : list
            List of Sequence of feature values representing a single data point.
        compress : bool, default False
            Whether to compress the request body.
        max_retries : int, default 5
            Maximum number of times to retry a request on a connection failure.

        Returns
        -------
        prediction : dict or None
            Output returned by the deployed model for `x`. If the prediction request returns an
            error, None is returned instead as a silent failure.

        """
        for i_retry in range(max_retries):
            response = self._predict(x, compress)
            if response.ok:
                return response.json()
            elif response.status_code == 502: # bad gateway; the error happened in the model backend
                data = response.json()
                if 'message' not in data:
                    raise RuntimeError("server error (no specific error message found)")
                raise RuntimeError("got error message from backend:\n" + data['message'])
            elif response.status_code >= 500 or response.status_code == 429:
                sleep = 0.3*(2**i_retry)  # 5 retries is 9.3 seconds total
                print("received status {}; retrying in {:.1f}s".format(response.status_code, sleep))
                time.sleep(sleep)
            else:
                break
        response.raise_for_status()
