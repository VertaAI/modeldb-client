# -*- coding: utf-8 -*-

from __future__ import division

import six

import copy


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
        raise NotImplementedError

    def reduce_on_input(self, state, input):
        """
        Updates `state` with `input`.

        Parameters
        ----------
        state : dict
            Current state of the histogram.
        input : dict
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
        prediction : dict
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
        raise NotImplementedError

    def get_from_state(self, state):
        raise NotImplementedError


class _HistogramProcessor(_BaseProcessor):
    """
    Object for processing histogram states and handling incoming values.

    """
    def reduce_states(self, state1, state2):
        """
        Combines `state1` and `state2`.

        Parameters
        ----------
        state1 : dict
            Current state of a histogram.
        state2 : dict
            Current state of a histogram.

        Returns
        -------
        dict
            Combination of `state1` and `state2`.

        Raises
        ------
        ValueError
            If `state1` and `state2` have incompatible bins.

        """
        if len(state1['bins']) != len(state2['bins']):
            raise ValueError("states have unidentical numbers of bins")

        state = copy.deepcopy(state1)
        for bin, state2_bin in zip(state['bins'], state2['bins']):
            for distribution_name, count in six.viewitems(state2_bin['counts']):
                bin['counts'][distribution_name] = bin['counts'].get(distribution_name, 0) + count

        return state


class _FloatHistogramProcessor(_HistogramProcessor):
    """
    :class:`HistogramProcessor` for continuous data.

    Parameters
    ----------
    feature_name : str
        Name of the feature to track in the histogram.
    bin_boundaries : list of float of length N+1
        Boundaries for the histogram's N bins.
    reference_counts : list of int of length N
        Counts for a precomputed reference distribution.

    """
    def __init__(self, feature_name, bin_boundaries, reference_counts, **kwargs):
        if len(bin_boundaries) - 1 != len(reference_counts):
            raise ValueError("`bin_boundaries` must be one element longer than `reference_counts`")

        kwargs['feature_name'] = feature_name
        kwargs['bin_boundaries'] = bin_boundaries
        kwargs['reference_counts'] = reference_counts
        super(_FloatHistogramProcessor, self).__init__(**kwargs)

    def _reduce_data(self, state, data):
        distribution_name = "live"

        # get feature value
        feature_name = self.config['feature_name']
        try:
            feature_val = data[feature_name]
        except KeyError:
            six.raise_from(KeyError("key '{}' not found in data".format(feature_name)), None)
        except TypeError:  # data is list instead of dict
            try:
                feature_index = self.config['feature_index']
            except KeyError:
                six.raise_from(RuntimeError("data is a list, but this Processor"
                                            " doesn't have an index for its feature"), None)
            try:
                feature_val = data[feature_index]
            except IndexError:
                six.raise_from(IndexError("index '{}' out of bounds for"
                                          " data of length {}".format(feature_index, len(data))), None)

        # fold feature value into state
        lower_bounds = [float('-inf')] + self.config['bin_boundaries']
        upper_bounds = self.config['bin_boundaries'] + [float('inf')]
        for bin, lower_bound, upper_bound in zip(state['bins'], lower_bounds, upper_bounds):
            if lower_bound <= feature_val < upper_bound:
                bin['counts'][distribution_name] = bin['counts'].get(distribution_name, 0) + 1
                return state
        else:  # this should only happen by developer error
            raise RuntimeError("unable to find appropriate bin;"
                               " `state` is probably somehow missing its out-of-bounds bins")

    def new_state(self):
        """
        Returns a new state as configured by `self.config`.

        Returns
        -------
        dict
            New histogram state.

        """
        state = {}

        # initialize empty bins
        state['bins'] = [{'counts': {}} for _ in range(len(self.config['bin_boundaries']) + 1)]

        return state

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
        if not state:
            state = self.new_state()

        return {
            'type': "float",
            'histogram': {
                'float': {
                    'live': [bin['counts'].get('live', 0) for bin in state['bins']],
                    'reference': [0] + self.config['reference_counts'] + [0],
                    'bucket_limits': [-1] + self.config['bin_boundaries'] + [-1],
                }
            }
        }


# TODO: have this subclass a future `CategoricalHistogramProcessor`
class _BinaryHistogramProcessor(_HistogramProcessor):
    """
    :class:`HistogramProcessor` for binary data.

    Parameters
    ----------
    feature_name : str
        Name of the feature to track in the histogram.
    reference_counts : list of int of length 2
        Counts for a precomputed reference distribution.

    """
    def __init__(self, feature_name, reference_counts, **kwargs):
        if len(reference_counts) != 2:
            raise ValueError("`reference_counts` must contain exactly two elements")

        kwargs['feature_name'] = feature_name
        kwargs['bin_categories'] = [0, 1]
        kwargs['reference_counts'] = reference_counts
        super(_BinaryHistogramProcessor, self).__init__(**kwargs)

    def _reduce_data(self, state, data):
        distribution_name = "live"

        # get feature value
        feature_name = self.config['feature_name']
        try:
            feature_val = data[feature_name]
        except KeyError:
            six.raise_from(KeyError("key '{}' not found in data".format(feature_name)), None)
        except TypeError:  # data is list instead of dict
            try:
                feature_index = self.config['feature_index']
            except KeyError:
                six.raise_from(RuntimeError("data is a list, but this Processor"
                                            " doesn't have an index for its feature"), None)
            try:
                feature_val = data[feature_index]
            except IndexError:
                six.raise_from(IndexError("index '{}' out of bounds for"
                                          " data of length {}".format(feature_index, len(data))), None)

        # fold feature value into state
        for bin, category in zip(state['bins'], self.config['bin_categories']):
            if feature_val == category:
                bin['counts'][distribution_name] = bin['counts'].get(distribution_name, 0) + 1
                break
        else:  # data doesn't match any category
            state['invalid_values'] += 1

        return state

    def new_state(self):
        state = {}

        # initialize empty bins
        state['bins'] = [{'counts': {}} for _ in range(len(self.config['bin_categories']))]

        # initialize invalid value count
        state['invalid_values'] = 0

        return state

    def reduce_states(self, state1, state2):
        state = super(_BinaryHistogramProcessor, self).reduce_states(state1, state2)

        state['invalid_values'] = state1['invalid_values'] + state2['invalid_values']

        return state

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
        if not state:
            state = self.new_state()

        return {
            'type': "binary",
            'histogram': {
                'binary': {
                    'live': [bin['counts'].get('live', 0) for bin in state['bins']],
                    'reference': self.config['reference_counts'],
                },
            },
        }


class FloatInputHistogramProcessor(_FloatHistogramProcessor):
    def reduce_on_input(self, state, input):
        return self._reduce_data(state, input)


class FloatPredictionHistogramProcessor(_FloatHistogramProcessor):
    def reduce_on_prediction(self, state, prediction):
        return self._reduce_data(state, prediction)


class BinaryInputHistogramProcessor(_BinaryHistogramProcessor):
    def reduce_on_input(self, state, input):
        return self._reduce_data(state, input)


class BinaryPredictionHistogramProcessor(_BinaryHistogramProcessor):
    def reduce_on_prediction(self, state, prediction):
        return self._reduce_data(state, prediction)
