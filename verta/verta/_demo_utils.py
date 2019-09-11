# -*- coding: utf-8 -*-

import six
from six.moves.urllib.parse import urljoin, urlparse

import json
import gzip
import os
import time

import requests

from . import _utils


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
        Hostname of the node running the Verta backend, e.g. "app.verta.ai".
    model_id : str, optional
        ID of the deployed ExperimentRun/ModelRecord.

    """
    _GRPC_PREFIX = "Grpc-Metadata-"

    def __init__(self, socket, model_id):
        back_end_url = urlparse(socket)
        self._scheme = back_end_url.scheme or "https"
        self._socket = back_end_url.netloc + back_end_url.path.rstrip('/')

        self._id = model_id
        self._status_url = "{}://{}/api/v1/deployment/status/{}".format(self._scheme, self._socket, model_id)

        self._prediction_url = None

        self._session = requests.Session()

        self._auth = {self._GRPC_PREFIX+'email': os.environ.get('VERTA_EMAIL'),
                      self._GRPC_PREFIX+'developer_key': os.environ.get('VERTA_DEV_KEY'),
                      self._GRPC_PREFIX+'source': "PythonClient"}

    def __repr__(self):
        return "<Model {}>".format(self._id)

    @classmethod
    def from_url(cls, url, token):
        """
        Returns a :class:`ModelAPI` based on a custom URL and token.

        Parameters
        ----------
        url : str, optional
            Prediction endpoint URL or path. Can be copy and pasted directly from the Verta Web App.
        token : str, optional
            Prediction token. Can be copy and pasted directly from the Verta Web App.

        Returns
        -------
        :class:`DeployedModel`

        """
        parsed_url = urlparse(url)

        deployed_model = cls(parsed_url.netloc, "")
        deployed_model._id = None
        deployed_model._status_url = None

        deployed_model._prediction_url = urljoin("{}://{}".format(parsed_url.scheme, parsed_url.netloc), parsed_url.path)
        deployed_model._session.headers['Access-Token'] = token

        return deployed_model

    def _set_token_and_url(self):
        response = self._session.get(self._status_url)
        _utils.raise_for_http_error(response)
        status = response.json()
        if status['status'] == 'error':
            raise RuntimeError(status['message'])
        if 'token' in status and 'api' in status:
            self._session.headers['Access-Token'] = status['token']
            self._prediction_url = urljoin("{}://{}".format(self._scheme, self._socket), status['api'])
        else:
            raise RuntimeError("token not found in status endpoint response; deployment may not be ready")

    def _predict(self, x, compress=False):
        """This is like ``DeployedModel.predict()``, but returns the raw ``Response`` for debugging."""
        if 'Access-token' not in self._session.headers or self._prediction_url is None:
            self._set_token_and_url()

        if compress:
            # create gzip
            gzstream = six.BytesIO()
            with gzip.GzipFile(fileobj=gzstream, mode='wb') as gzf:
                gzf.write(six.ensure_binary(json.dumps(x)))
            gzstream.seek(0)

            return self._session.post(
                self._prediction_url,
                headers={'Content-Encoding': 'gzip'},
                data=gzstream.read(),
            )
        else:
            return self._session.post(self._prediction_url, json=x)

    @property
    def is_deployed(self):
        response = self._session.get(self._status_url)
        return response.ok and 'token' in response.json()

    def predict(self, x, compress=False, max_retries=5):
        """
        Make a prediction using input `x`.

        Parameters
        ----------
        x : list
            A batch of inputs for the model.
        compress : bool, default False
            Whether to compress the request body.
        max_retries : int, default 5
            Maximum number of times to retry a request on a connection failure.

        Returns
        -------
        prediction : dict or None
            Output returned by the deployed model for `x`.

        Raises
        ------
        RuntimeError
            If the deployed model encounters an error while running a prediction.

        """
        for i_retry in range(max_retries):
            response = self._predict(x, compress)
            if response.ok:
                return response.json()
            elif response.status_code == 502: # bad gateway; the error happened in the model backend
                data = response.json()
                raise RuntimeError("back end encountered an error: {}"
                                   .format(data.get('message', "(no specific error message found)")))
            elif response.status_code >= 500 or response.status_code == 429:
                sleep = 0.3*(2**i_retry)  # 5 retries is 9.3 seconds total
                print("received status {}; retrying in {:.1f}s".format(response.status_code, sleep))
                time.sleep(sleep)
            else:
                break
        _utils.raise_for_http_error(response)
