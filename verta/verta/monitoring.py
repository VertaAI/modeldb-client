# -*- coding: utf-8 -*-

from __future__ import division

import six


def calculate_bin_boundaries(data, num_bins=10):
    """
    Calculates boundaries for `num_bins` equally-spaced histogram bins.

    Parameters
    ----------
    data : sequence of numbers
        Numerical data to be binned.
    num_bins : int, default 10
        Number of bins to use.

    Returns
    -------
    list of float

    """
    start, stop = min(data), max(data)
    space = (stop - start)/num_bins
    return [start + space*i for i in range(num_bins+1)]


def calculate_reference_counts(data, bin_boundaries):
    """
    Fits `data` into the histogram bins defined by `bin_boundaries`.

    Parameters
    ----------
    data : sequence of numbers
        Numerical data to be binned.
    bin_boundaries : list of float of length N+1
        Boundaries for a histogram's N bins.

    Returns
    -------
    list of float of length N
        Counts of `data` values in each bin defined by `bin_boundaries`.

    Raises
    ------
    ValueError
        If `data` contains a value outside the range defined by `bin_boundaries`.

    """
    # TODO: there is definitely a faster way to do this
    reference_counts = []
    for l, r in zip(bin_boundaries[:-1], bin_boundaries[1:]):
        count = len([datum for datum in data if l <= datum < r])
        reference_counts.append(count)

    return reference_counts


class _BaseProcessor(object):
    def __init__(self, **kwargs):
        self.config = kwargs

    def new_state(self):
        """
        Returns a new state as configured by `self.config`.

        Returns
        -------
        dict
            New histogram state.

        """
        raise NotImplementedError

    def reduce_on_input(self, state, input):
        """
        Updates `state` with `input`.

        Parameters
        ----------
        state : dict
            Current state of the histogram.
        input : JSON object
            JSON data containing the feature value.

        Returns
        -------
        dict
            Updated histogram state.

        """
        raise NotImplementedError

    def reduce_on_prediction(self, state, prediction):
        """
        Updates `state` with `prediction`.

        Parameters
        ----------
        state : dict
            Current state of the histogram.
        prediction : JSON object
            JSON data containing the feature value.

        Returns
        -------
        dict
            Updated histogram state.

        """
        raise NotImplementedError

    def reduce_on_ground_truth(self, state, prediction, ground_truth):
        raise NotImplementedError

    def reduce_states(self, state1, state2):
        """
        Merges `state2` into `state1`.

        Parameters
        ----------
        state1 : dict
            Current state of a histogram.
        state2 : dict
            Current state of a histogram.

        Returns
        -------
        dict
            Modified `state1`, with `state2` merged in.

        Raises
        ------
        ValueError
            If `state1` and `state2` are incompatible.

        """
        raise NotImplementedError

    def get_from_state(self, state):
        """
        Returns a well-structured representation of `state` and `self.config`.

        Parameters
        ----------
        state : dict
            Current state of the histogram.

        Returns
        -------
        dict
            JSON data.

        """
        raise NotImplementedError


class _HistogramProcessor(_BaseProcessor):
    """
    Object for processing histogram states and handling incoming values.

    """
    def _get_feature_value(self, data):
        feature_name = self.config['feature_name']
        if isinstance(data, dict):
            feature_val = data.get(feature_name, None)
        elif isinstance(data, list):
            feature_index = self.config['feature_index']
            if feature_index is None:
                raise TypeError("data is a list, but this Processor"
                                " doesn't have an index for its feature")
            try:
                feature_val = data[feature_index]
            except IndexError:
                six.raise_from(IndexError("index '{}' out of bounds for"
                                          " data of length {}".format(feature_index, len(data))), None)
        elif feature_name is None and feature_index is None:  # probably intentional scalar
            feature_val = data
        else:
            raise TypeError("data {} is neither a dict nor a list".format(data))

        return feature_val

    def reduce_states(self, state1, state2):
        if len(state1['bins']) != len(state2['bins']):
            raise ValueError("states have unidentical numbers of bins")

        for i, state2_bin in enumerate(state2['bins']):
            state1['bins'][i] += state2_bin

        return state1


class _FloatHistogramProcessor(_HistogramProcessor):
    """
    :class:`HistogramProcessor` for continuous data.

    Parameters
    ----------
    bin_boundaries : list of float of length N+1
        Boundaries for the histogram's N bins.
    reference_counts : list of int of length N, optional
        Counts for a precomputed reference distribution.
    feature_name : str, optional
        Name of the feature to track in the histogram.
    feature_index : int, optional
        Index of the feature for when the data is passed as a list instead of a dictionary.

    """
    def __init__(self, bin_boundaries, reference_counts=None, feature_name=None, feature_index=None, **kwargs):
        if (reference_counts is not None
                and len(bin_boundaries) - 1 != len(reference_counts)):
            raise ValueError("`bin_boundaries` must be one element longer than `reference_counts`")

        kwargs['bin_boundaries'] = bin_boundaries
        kwargs['reference_counts'] = reference_counts
        kwargs['feature_name'] = feature_name
        kwargs['feature_index'] = feature_index
        super(_FloatHistogramProcessor, self).__init__(**kwargs)

    def _reduce_data(self, state, data):
        feature_val = self._get_feature_value(data)

        if feature_val is None:  # missing data
            return state

        # fold feature value into state
        lower_bounds = [float('-inf')] + self.config['bin_boundaries']
        upper_bounds = self.config['bin_boundaries'] + [float('inf')]
        for i, (lower_bound, upper_bound) in enumerate(zip(lower_bounds, upper_bounds)):
            if lower_bound <= feature_val < upper_bound:
                state['bins'][i] += 1
                return state
        else:  # this should only happen by developer error
            raise RuntimeError("unable to find appropriate bin;"
                               " `state` is probably somehow missing its out-of-bounds bins")

    def new_state(self):
        state = {}

        # initialize empty bins
        state['bins'] = [0 for _ in range(len(self.config['bin_boundaries']) + 1)]

        return state

    def get_from_state(self, state):
        if not state:
            state = self.new_state()

        histogram = {}
        histogram['live'] = state['bins']
        if self.config['reference_counts'] is not None:
            histogram['reference'] = [0] + self.config['reference_counts'] + [0]
        histogram['bucket_limits'] = [-1] + self.config['bin_boundaries'] + [-1]

        return {
            'type': "float",
            'histogram': {
                'float': histogram,
            },
        }


class _DiscreteHistogramProcessor(_HistogramProcessor):
    """
    :class:`HistogramProcessor` for discrete data.

    Parameters
    ----------
    bin_categories : list of length N
        Category values for the histogram's bins.
    reference_counts : list of int of length N, optional
        Counts for a precomputed reference distribution.
    feature_name : str, optional
        Name of the feature to track in the histogram.
    feature_index : int, optional
        Index of the feature for when the data is passed as a list instead of a dictionary.

    """
    def __init__(self, bin_categories, reference_counts=None, feature_name=None, feature_index=None, **kwargs):
        if (reference_counts is not None
                and len(bin_categories) != len(reference_counts)):
            raise ValueError("`bin_boundaries` and `reference_counts` must have the same length")

        kwargs['bin_categories'] = bin_categories
        kwargs['reference_counts'] = reference_counts
        kwargs['feature_name'] = feature_name
        kwargs['feature_index'] = feature_index
        super(_DiscreteHistogramProcessor, self).__init__(**kwargs)

    def _reduce_data(self, state, data):
        feature_val = self._get_feature_value(data)

        if feature_val is None:  # missing data
            return state

        # fold feature value into state
        for i, category in enumerate(self.config['bin_categories']):
            if feature_val == category:
                state['bins'][i] += 1
                break
        else:  # data doesn't match any category
            state['invalid_values'] += 1

        return state

    def new_state(self):
        state = {}

        # initialize empty bins
        state['bins'] = [0 for _ in range(len(self.config['bin_categories']))]

        # initialize invalid value count
        state['invalid_values'] = 0

        return state

    def reduce_states(self, state1, state2):
        state1 = super(_DiscreteHistogramProcessor, self).reduce_states(state1, state2)

        state1['invalid_values'] = state1['invalid_values'] + state2['invalid_values']

        return state1

    def get_from_state(self, state):
        if not state:
            state = self.new_state()

        histogram = {}
        histogram['live'] = state['bins']
        if self.config['reference_counts'] is not None:
            histogram['reference'] = self.config['reference_counts']
        histogram['bucket_values'] = self.config['bin_categories']
        histogram['live_miss_count'] = state['invalid_values']

        return {
            'type': "discrete",
            'histogram': {
                'discrete': histogram,
            },
        }


class _BinaryHistogramProcessor(_DiscreteHistogramProcessor):
    """
    :class:`HistogramProcessor` for binary data.

    Parameters
    ----------
    reference_counts : list of int of length 2, optional
        Counts for a precomputed reference distribution.
    feature_name : str, optional
        Name of the feature to track in the histogram.
    feature_index : int, optional
        Index of the feature for when the data is passed as a list instead of a dictionary.

    """
    def __init__(self, reference_counts=None, feature_name=None, feature_index=None, **kwargs):
        if (reference_counts is not None
                and len(reference_counts) != 2):
            raise ValueError("`reference_counts` must contain exactly two elements")

        kwargs['bin_categories'] = [0, 1]
        kwargs['reference_counts'] = reference_counts
        kwargs['feature_name'] = feature_name
        kwargs['feature_index'] = feature_index
        super(_BinaryHistogramProcessor, self).__init__(**kwargs)

    def get_from_state(self, state):
        if not state:
            state = self.new_state()

        histogram = {}
        histogram['live'] = state['bins']
        if self.config['reference_counts'] is not None:
            histogram['reference'] = self.config['reference_counts']

        return {
            'type': "binary",
            'histogram': {
                'binary': histogram,
            },
        }


class FloatInputHistogramProcessor(_FloatHistogramProcessor):
    def reduce_on_input(self, state, input):
        return self._reduce_data(state, input)


class FloatPredictionHistogramProcessor(_FloatHistogramProcessor):
    def reduce_on_prediction(self, state, prediction):
        return self._reduce_data(state, prediction)


class DiscreteInputHistogramProcessor(_DiscreteHistogramProcessor):
    def reduce_on_input(self, state, input):
        return self._reduce_data(state, input)


class DiscretePredictionHistogramProcessor(_DiscreteHistogramProcessor):
    def reduce_on_prediction(self, state, prediction):
        return self._reduce_data(state, prediction)


class BinaryInputHistogramProcessor(_BinaryHistogramProcessor):
    def reduce_on_input(self, state, input):
        return self._reduce_data(state, input)


class BinaryPredictionHistogramProcessor(_BinaryHistogramProcessor):
    def reduce_on_prediction(self, state, prediction):
        return self._reduce_data(state, prediction)
