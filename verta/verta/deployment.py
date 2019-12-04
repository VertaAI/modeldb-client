# -*- coding: utf-8 -*-

from . import _six
from ._six.moves.urllib.parse import urljoin, urlparse  # pylint: disable=import-error, no-name-in-module

import json
import gzip
import os
import time
import warnings

import requests

from .client import _GRPC_PREFIX
from . import _utils


class DeployedModel:
    """
    Object for interacting with deployed models.

    .. deprecated:: 0.13.7
        The `socket` parameter will be renamed to `host` in v0.14.0
    .. deprecated:: 0.13.7
        The `model_id` parameter will be renamed to `run_id` in v0.14.0

    This class provides functionality for sending predictions to a deployed model on the Verta
    backend.

    Authentication credentials must be present in the environment through `$VERTA_EMAIL` and
    `$VERTA_DEV_KEY`.

    Parameters
    ----------
    host : str
        Hostname of the Verta Web App.
    run_id : str
        ID of the deployed ExperimentRun.

    Examples
    --------
    >>> # host == "https://app.verta.ai/"
    >>> # run.id == "01234567-0123-0123-0123-012345678901"
    >>> DeployedModel(
    ...     host="https://app.verta.ai/",
    ...     run_id="01234567-0123-0123-0123-012345678901",
    ... )
    <DeployedModel 01234567-0123-0123-0123-012345678901>

    """
    def __init__(self, _host=None, _run_id=None, _from_url=False, **kwargs):
        # this is to temporarily maintain compatibility with anyone passing in `socket` and `model_id` as kwargs
        # TODO v0.14.0: instate `host` and `run_id` params
        # TODO v0.14.0: remove the following block of param checks
        # TODO v0.14.0: put automodule verta.deployment back on ReadTheDocs
        if 'socket' in kwargs:
            warnings.warn("`socket` will be renamed to `host` in an upcoming version",
                          category=FutureWarning)
        if 'model_id' in kwargs:
            warnings.warn("`model_id` will be renamed to `run_id` in an upcoming version",
                          category=FutureWarning)
        host = kwargs.get('host', kwargs.get('socket', _host))
        run_id = kwargs.get('run_id', kwargs.get('model_id', _run_id))
        if host is None:
            raise TypeError("missing required argument: `host`")
        if run_id is None:
            raise TypeError("missing required argument: `run_id`")

        self._session = requests.Session()
        if not _from_url:
            self._session.headers.update({_GRPC_PREFIX+'source': "PythonClient"})
            try:
                self._session.headers.update({_GRPC_PREFIX+'email': os.environ['VERTA_EMAIL']})
            except KeyError:
                _six.raise_from(EnvironmentError("${} not found in environment".format('VERTA_EMAIL')), None)
            try:
                self._session.headers.update({_GRPC_PREFIX+'developer_key': os.environ['VERTA_DEV_KEY']})
            except KeyError:
                _six.raise_from(EnvironmentError("${} not found in environment".format('VERTA_DEV_KEY')), None)

        back_end_url = urlparse(host)
        self._scheme = back_end_url.scheme or "https"
        self._socket = back_end_url.netloc + back_end_url.path.rstrip('/')

        self._id = run_id
        self._status_url = "{}://{}/api/v1/deployment/status/{}".format(self._scheme, self._socket, self._id)

        self._prediction_url = None

    def __repr__(self):
        if self._id is not None:
            return "<{} {}>".format(self.__class__.__name__, self._id)
        elif self._prediction_url:
            return "<{} at {}>".format(self.__class__.__name__, self._prediction_url)
        else:  # if someone's messing with the object's state
            return "<{}>".format(self.__class__.__name__)

    @classmethod
    def from_url(cls, url, token=None):
        """
        Returns a :class:`DeployedModel` based on a custom URL and token.

        Parameters
        ----------
        url : str
            Full prediction endpoint URL. Can be copy and pasted directly from the Verta Web App.
        token : str, optional
            Prediction token. Can be copy and pasted directly from the Verta Web App.

        Returns
        -------
        :class:`DeployedModel`

        Examples
        --------
        >>> # run.id == "01234567-0123-0123-0123-012345678901"
        >>> # token == "abcdefgh-abcd-abcd-abcd-abcdefghijkl"
        >>> DeployedModel.from_url(
        ...     url="https://app.verta.ai/api/v1/predict/01234567-0123-0123-0123-012345678901",
        ...     token="abcdefgh-abcd-abcd-abcd-abcdefghijkl",
        ... )
        <DeployedModel at https://app.verta.ai/api/v1/predict/01234567-0123-0123-0123-012345678901>

        """
        parsed_url = urlparse(url)

        deployed_model = cls(parsed_url.netloc, "", _from_url=True)
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
        elif status['status'] != 'deployed':
            raise RuntimeError("model is not yet ready, or has not yet been deployed")
        else:
            self._session.headers['Access-Token'] = status.get('token')
            self._prediction_url = urljoin("{}://{}".format(self._scheme, self._socket), status['api'])

    def _predict(self, x, compress=False):
        """This is like ``DeployedModel.predict()``, but returns the raw ``Response`` for debugging."""
        if 'Access-token' not in self._session.headers or self._prediction_url is None:
            self._set_token_and_url()

        if compress:
            # create gzip
            gzstream = _six.BytesIO()
            with gzip.GzipFile(fileobj=gzstream, mode='wb') as gzf:
                gzf.write(_six.ensure_binary(json.dumps(x)))
            gzstream.seek(0)

            return self._session.post(
                self._prediction_url,
                headers={'Content-Encoding': 'gzip'},
                data=gzstream.read(),
            )
        else:
            return self._session.post(self._prediction_url, json=x)

    def predict(self, x, compress=False, max_retries=5, always_retry_404=True, always_retry_429=True):
        """
        Make a prediction using input `x`.

        .. versionadded:: 0.13.14
           The `always_retry_404` parameter.
        .. versionadded:: 0.13.12
           The `always_retry_429` parameter.

        Parameters
        ----------
        x : list
            A batch of inputs for the model.
        compress : bool, default False
            Whether to compress the request body.
        max_retries : int, default 5
            Maximum number of times to retry a request on a connection failure.
        always_retry_404 : bool, default True
            Whether to retry on 404s indefinitely. This is to accommodate model deployment warm-up.
        always_retry_429 : bool, default True
            Whether to retry on 429s indefinitely. This is to accommodate third-party cluster
            autoscalers, which may take minutes to launch new pods for servicing requests.

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
        num_retries = 0
        while num_retries < max_retries:
            response = self._predict(x, compress)

            if response.ok:
                return response.json()
            elif response.status_code == 502:  # bad gateway; possibly error from the model back end
                try:
                    data = response.json()
                except ValueError:  # not JSON response; 502 not from model back end
                    pass
                else:  # from model back end; contains message (maybe)
                    msg = data.get('message', "(no specific error message found)")
                    raise RuntimeError("deployed model encountered an error: {}".format(msg))
            elif not (response.status_code >= 500 or response.status_code in (404, 429)):  # clientside error
                break

            sleep = 0.3*(2**(num_retries + 1))
            print("received status {}; retrying in {:.1f}s".format(response.status_code, sleep))
            time.sleep(sleep)
            if ((response.status_code == 404 and always_retry_404)  # model warm-up
                    or (response.status_code == 429 and always_retry_429)):  # too many requests
                num_retries = min(num_retries + 1, max_retries - 1)
            else:
                num_retries += 1

        _utils.raise_for_http_error(response)
