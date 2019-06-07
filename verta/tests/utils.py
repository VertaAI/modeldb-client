import random
from string import printable

import requests

import verta._utils

from hypothesis import strategies as st


def gen_none():
    return None


def gen_bool():
    return random.random() > .5


def gen_float(start=1, stop=None):
    if stop is None:
        return random.random()*start
    else:
        return random.uniform(start, stop)


def gen_int(start=10, stop=None):
    return random.randrange(start, stop)


def gen_str(length=8):
    return ''.join([chr(random.randrange(97, 123))
                    for _
                    in range(length)])


def gen_list(length=8):
    """Generates a list with mixed-type elements."""
    gen_el = lambda fns=(gen_none, gen_bool, gen_float, gen_int, gen_str): random.choice(fns)()
    return [gen_el() for _ in range(length)]


def gen_dict(length=8):
    """Generates a single-level dict with string keys and mixed-type values."""
    gen_val = lambda fns=(gen_none, gen_bool, gen_float, gen_int, gen_str): random.choice(fns)()
    res = {}
    while len(res) < length:
        res[gen_str()] = gen_val()
    return res


@st.composite
def st_scalars(draw):
    return draw(st.none()
              | st.booleans()
              | st.integers()
              | st.floats(allow_nan=False, allow_infinity=False)
              | st.text(printable))


@st.composite
def st_json(draw, max_size=6):
    return draw(st.recursive(st_scalars(),
                             lambda children: st.lists(children,
                                                       min_size=1,
                                                       max_size=max_size)
                                            | st.dictionaries(st.text(printable),
                                                              children,
                                                              min_size=1,
                                                              max_size=max_size)))


@st.composite
def st_keys(draw):
    return draw(st.text(sorted(verta._utils._VALID_FLAT_KEY_CHARS), min_size=1))


@st.composite
def st_key_values(draw, min_size=1, max_size=12, scalars_only=False):
    return draw(st.dictionaries(st_keys(),
                                st_scalars() if scalars_only else st_json(),
                                min_size=min_size,
                                max_size=max_size))


def delete_project(id_, client):
    request_url = "{}://{}/v1/project/deleteProject".format(client._scheme, client._socket)
    response = requests.delete(request_url, json={'id': id_}, headers=client._auth)
    response.raise_for_status()


def delete_experiment(id_, client):
    request_url = "{}://{}/v1/experiment/deleteExperiment".format(client._scheme, client._socket)
    response = requests.delete(request_url, json={'id': id_}, headers=client._auth)
    response.raise_for_status()


def delete_experiment_run(id_, client):
    request_url = "{}://{}/v1/experiment-run/deleteExperimentRun".format(client._scheme, client._socket)
    response = requests.delete(request_url, json={'id': id_}, headers=client._auth)
    response.raise_for_status()
