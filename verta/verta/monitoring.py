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

    Returns
    -------
    list of float
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


class ProcessorBase(object):
    def __init__(self, config=None):
        self.config = config

    def new_state(self):
        raise NotImplementedError

    def reduce_on_input(self, state, input):
        raise NotImplementedError

    def reduce_on_prediction(self, state, prediction):
        raise NotImplementedError

    def reduce_on_ground_truth(self, state, prediction, ground_truth):
        raise NotImplementedError

    def reduce_states(self, state1, state2):
        raise NotImplementedError

    def get_from_state(self, state):
        raise NotImplementedError


class HistogramProcessor(ProcessorBase):
    """
    Object for processing histogram states and handling new inputs.

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
        super(HistogramProcessor, self).__init__(kwargs)

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
        state['bins'] = []
        bounds = self.config['bin_boundaries']
        for lower_bound, upper_bound in zip(bounds[:-1], bounds[1:]):
            state['bins'].append({
                'bounds': {'lower': lower_bound,
                           'upper': upper_bound},
                'counts': {},
            })

        # fill reference bins
        for bin, reference_count in zip(state['bins'], self.config['reference_counts']):
            bin['counts']['Reference'] = reference_count

        # initialize out-of-bounds bins
        state['bins'].insert(0, {
            'bounds': {'upper': state['bins'][0]['bounds']['lower']},
            'counts': {},
        })
        state['bins'].append({
            'bounds': {'lower': state['bins'][-1]['bounds']['upper']},
            'counts': {},
        })

        return state

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
        distribution_name = "Live"
        state = copy.deepcopy(state)

        feature_name = self.config['feature_name']
        try:
            feature_val = input[feature_name]
        except KeyError as e:
            six.raise_from(KeyError("key '{}' not found in `input`".format(e.args[0])), None)

        for bin in state['bins']:
            lower_bound = bin['bounds'].get('lower', float('-inf'))
            upper_bound = bin['bounds'].get('upper', float('inf'))
            if lower_bound <= feature_val < upper_bound:
                bin['counts'][distribution_name] = bin['counts'].get(distribution_name, 0) + 1
                return state
        else:
            raise RuntimeError("unable to find appropriate bin; `state` is probably missing its out-of-bounds bins")

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
        for bin1, bin2 in zip(state1['bins'], state2['bins']):
            if (bin1['bounds']['lower'] != bin2['bounds']['lower']
                    or bin1['bounds']['upper'] != bin2['bounds']['upper']):
                raise ValueError("states have unidentical bin boundaries")

        state = copy.deepcopy(state1)
        for i, bin in enumerate(state['bins']):
            for distribution_name, count in six.viewitems(state2['bins'][i]['counts']):
                bin['counts'][distribution_name] = bin['counts'].get(distribution_name, 0) + count

        return state

    def get_from_state(self, state):
        state_info = copy.deepcopy(state)

        # get all distribution names
        distribution_names = set()
        for bin in state['bins']:
            distribution_names.update(six.viewkeys(bin['counts']))
        state_info['distribution_names'] = list(distribution_names)

        return state_info
