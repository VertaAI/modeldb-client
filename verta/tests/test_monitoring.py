import six

import string

import numpy as np

from verta import monitoring

import pytest


class TestUtils:
    def test_bin_boundaries(self):
        for _ in range(360):
            start = np.random.randint(-10, 10)
            stop = start + np.random.randint(1, 10)
            num_bins = np.random.randint(5, 10)

            data = list(start + np.random.random(size=358)*(stop - start)) + [start, stop]

            assert np.linspace(start, stop, num_bins+1).tolist() \
                == monitoring.calculate_bin_boundaries(data, num_bins)

    def test_reference_counts(self):
        for _ in range(360):
            start = np.random.randint(-10, 10)
            stop = start + np.random.randint(1, 10)
            num_bins = np.random.randint(5, 10)

            data = list(start + np.random.random(size=358)*(stop - start)) + [start, stop]

            bin_boundaries = monitoring.calculate_bin_boundaries(data, num_bins)

            assert [sum((l <= np.array(data)) & (np.array(data) < r))
                    for l, r in zip(bin_boundaries[:-1], bin_boundaries[1:])] \
                == monitoring.calculate_reference_counts(data, bin_boundaries)
