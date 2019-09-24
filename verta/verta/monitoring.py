# -*- coding: utf-8 -*-

from __future__ import division

import six

import copy


class ProcessorBase(object):
    # Config carries any configuration to change the processor, such as references and bucket limits to use. It should not be changed during the computation.
    def __init__(self, config=None):
        self.config = config

    # Return a new state. This state is the aggregation of the computation.
    # The format and value depend on the processor and might rely on config, but
    # it must be serializable by json
    def new_state(self):
        pass

    # When there is an input, this method is called with the relevant state and the value of the feature.
    # If the feature is missing, then `feature_val` is None.
    # This method returns the new state.
    def reduce_on_input(self, state, feature_val):
        pass

    # When there is a prediction, this method is called with the relevant state and the value of the feature.
    # This method returns the new state.
    def reduce_on_prediction(self, state, prediction):
        pass

    # When a ground truth is associated with a sample, its value and the prediction associated are sent to this method.
    # This method returns the updated state.
    def reduce_on_ground_truth(self, state, prediction, ground_truth):
        pass

    # Given two states, combine them to create a valid accumulated state and return it.
    # This final state must be the same as if was called with the values that created `state1` and `state2`
    def reduce_states(self, state1, state2):
        pass

    # Given a state, returns a structured output that can give information about it.
    # For now, we only have visualization information.
    def get_from_state(self, state):
        pass


class HistogramProcessor(ProcessorBase):
    """


    Parameters
    ----------
    bin_boundaries : list of float of length N+1
        Boundaries for the histogram's N bins.
    reference_counts : list of int of length N
        Counts for a precomputed reference distribution.

    """
    def __init__(self, bin_boundaries, reference_counts, **kwargs):
        if len(bin_boundaries) - 1 != len(reference_counts):
            raise ValueError("`bin_boundaries` must be one element longer than `reference_counts`")

        kwargs['bin_boundaries'] = bin_boundaries
        kwargs['reference_counts'] = reference_counts
        super(HistogramProcessor, self).__init__(kwargs)

    def new_state(self):
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

    def reduce_on_input(self, state, feature_val):
        """


        Parameters
        ----------
        state : dict
            Current state of the histogram.
        feature_val : float or int or bool or str
            Value of the feature.

        """
        distribution_name = "Live"
        state = copy.deepcopy(state)

        for bin in state['bins']:
            lower_bound = bin['bounds'].get('lower', float('-inf'))
            upper_bound = bin['bounds'].get('upper', float('inf'))
            if lower_bound <= feature_val < upper_bound:
                bin['counts'][distribution_name] = bin['counts'].get(distribution_name, 0) + 1
                return state

    def reduce_states(self, state1, state2):
        """


        Parameters
        ----------
        state1 : dict
            Current state of a histogram.
        state2 : dict
            Current state of a histogram.

        Returns
        -------
        dict
            Combination of `state1` and `state2`

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
