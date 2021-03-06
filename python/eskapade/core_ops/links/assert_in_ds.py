# **********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                   *
# * Class  : AssertInDs                                                     *
# * Created: 2016/11/08                                                            *
# * Description:                                                                   *
# *      Algorithm that asserts that items exists in the datastore                 *
# *                                                                                *
# * Authors:                                                                       *
# *      KPMG Big Data team, Amstelveen, The Netherlands                           *
# *                                                                                *
# * Redistribution and use in source and binary forms, with or without             *
# * modification, are permitted according to the terms listed in the file          *
# * LICENSE.                                                                       *
# **********************************************************************************

from eskapade import ProcessManager, StatusCode, DataStore, Link


class AssertInDs(Link):
    """
    Asserts that specified item(s) exists in the datastore
    """

    def __init__(self, **kwargs):
        """
        Store the configuration of link AssertInDs

        :param str name: name of link
        :param lst keySet: list of keys to check
        """

        Link.__init__(self, kwargs.pop('name', 'AssertInDs'))

        # process and register all relevant kwargs. kwargs are added as attributes of the link.
        # second arg is default value for an attribute. key is popped from kwargs.
        self._process_kwargs(kwargs, keySet=[])        
        self.check_extra_kwargs(kwargs)

        return

    def execute(self):
        """ Execute AssertInDs """

        ds = ProcessManager().service(DataStore)

        for key in self.keySet:
            assert key in ds, 'Key %s not in DataStore.' % key

        return StatusCode.Success

