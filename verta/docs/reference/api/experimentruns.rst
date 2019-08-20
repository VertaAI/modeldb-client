ExperimentRuns
==============


.. autoclass:: verta.client.ExperimentRuns
    :members:

    .. describe:: len(runs)

        Returns the number of :class:`ExperimentRun`\ s in this collection.

    .. describe:: runs[run_id]

        Returns the :class:`ExperimentRun` in this collection with ID `run_id`. Raises a :exc:`KeyError` if
        `run_id` is not in the collection.

    .. describe:: runs + other

        Returns a new :class:`ExperimentRuns` that is the concatenation of this collection and `other`.
