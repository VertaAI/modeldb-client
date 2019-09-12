# -*- coding: utf-8 -*-

import six
from six.moves.urllib.parse import urljoin, urlparse

import json
import gzip
import os
import time

import requests

from .client import _GRPC_PREFIX
from . import _utils


class DeployedModel(object):
    """
    Object for interacting with deployed models.

    This class provides functionality for sending predictions to a deployed model on the Verta
    backend.

    Authentication credentials must be present in the environment through `$VERTA_EMAIL` and
    `$VERTA_DEV_KEY`.

    """
    def __init__(self, prediction_url, token):
        self._session = requests.Session()
        self._prediction_url = prediction_url
        self._session.headers['Access-Token'] = token

    def __repr__(self):
        return "<DeployedModel at {}>".format(self._prediction_url)

    # TODO: convert into classmethod when DeployedModel is no longer subclassed
    @staticmethod
    def from_id(run_id, host):
        """
        Returns a :class:`DeployedModel` based on an Experiment Run ID.

        Parameters
        ----------
        run_id : str
            ID of the deployed Experiment Run.
        host : str
            Hostname of the Verta Web App.

        Returns
        -------
        :class:`DeployedModel`

        Raises
        ------
        RuntimeError
            If the deployed model appears to not be ready.
        requests.HTTPError
            If the server encounters an error while handing the HTTP request.

        """
        try:
            auth = {_GRPC_PREFIX+'email': os.environ['VERTA_EMAIL'],
                    _GRPC_PREFIX+'developer_key': os.environ['VERTA_DEV_KEY'],
                    _GRPC_PREFIX+'source': "PythonClient"}
        except KeyError as e:
            key = e.args[0]
            six.raise_from(EnvironmentError("${} not found in environment".format(key)), None)

        parsed_url = urlparse(host)
        scheme = parsed_url.scheme or "https"
        socket = parsed_url.netloc + parsed_url.path.rstrip('/')
        status_url = "{}://{}/api/v1/deployment/status/{}".format(scheme, socket, run_id)
        prediction_url_prefix = "{}://{}".format(scheme, socket)

        # set token and prediction URL
        response = requests.get(status_url, headers=auth)
        _utils.raise_for_http_error(response)
        status = response.json()
        if 'token' in status and 'api' in status:
            prediction_url = urljoin(prediction_url_prefix, status['api'])
            return DeployedModel(prediction_url, status['token'])
        elif status.get('status') == 'error':
            raise RuntimeError(status.get('message', "message not found in status endpoint response; deployment may not be ready"))
        else:
            raise RuntimeError("token not found in status endpoint response; deployment may not be ready")

    # TODO: convert into classmethod when DeployedModel is no longer subclassed
    @staticmethod
    def from_url(url, token):
        """
        Returns a :class:`DeployedModel` based on a custom URL and token.

        Parameters
        ----------
        url : str, optional
            Prediction endpoint URL or path. Can be copied and pasted directly from the Verta Web App.
        token : str, optional
            Prediction token. Can be copied and pasted directly from the Verta Web App.

        Returns
        -------
        :class:`DeployedModel`

        """
        parsed_url = urlparse(url)
        prediction_url = urljoin("{}://{}".format(parsed_url.scheme, parsed_url.netloc), parsed_url.path)

        return DeployedModel(prediction_url, token)

    def _predict(self, x, compress=False):
        """This is like ``DeployedModel.predict()``, but returns the raw ``Response`` for debugging."""
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
        prediction : list
            Output returned by the deployed model for `x`.

        Raises
        ------
        RuntimeError
            If the deployed model encounters an error while running the prediction.
        requests.HTTPError
            If the server encounters an error while handing the HTTP request.

        """
        for i_retry in range(max_retries):
            response = self._predict(x, compress)
            if response.ok:
                return response.json()
            elif response.status_code == 502:  # bad gateway; the error happened in the model back end
                data = response.json()
                raise RuntimeError("deployed model encountered an error: {}"
                                   .format(data.get('message', "(no specific error message found)")))
            elif response.status_code >= 500 or response.status_code == 429:
                sleep = 0.3*(2**i_retry)  # 5 retries is 9.3 seconds total
                print("received status {}; retrying in {:.1f}s".format(response.status_code, sleep))
                time.sleep(sleep)
            else:
                break
        _utils.raise_for_http_error(response)
