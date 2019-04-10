import six


if six.PY2:
    from urlparse import urlparse

elif six.PY3:
    from urllib.parse import urlparse
