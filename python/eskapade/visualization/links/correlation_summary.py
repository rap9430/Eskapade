# **********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                   *
# * Class  : correlation_summary                                                   *
# * Created: 2017/03/13                                                            *
# * Description:                                                                   *
# *      Algorithm to do create correlation heatmaps                               *
# *                                                                                *
# * Authors:                                                                       *
# *      KPMG Big Data team, Amstelveen, The Netherlands                           *
# *                                                                                *
# * Redistribution and use in source and binary forms, with or without             *
# * modification, are permitted according to the terms listed in the file          *
# * LICENSE.                                                                       *
# **********************************************************************************

import os
import pandas as pd
import numpy as np
import tabulate
#from sklearn.feature_selection import mutual_info_regression

from eskapade import ProcessManager, ConfigObject, Link, DataStore, StatusCode
from eskapade.core import persistence
from eskapade import visualization

#ALL_CORRS = ['pearson', 'kendall', 'spearman', 'mutual_information', 'correlation_ratio']
ALL_CORRS = ['pearson', 'kendall', 'spearman', 'correlation_ratio']
LINEAR_CORRS = ['pearson', 'kendall', 'spearman']


class CorrelationSummary(Link):
    """Create a heatmap of correlations between dataframe variables"""

    def __init__(self, **kwargs):
        """Initialize CorrelationSummary instance

        :param str name: name of link
        :param str read_key: key of input dataframe to read from data store
        :param str store_key: key of correlations dataframe in data store
        :param str results_path: path to save correlation summary pdf
        :param list methods: method(s) of computing correlations
        :param str pages_key: data store key of existing report pages
        """

        # initialize Link, pass name from kwargs
        Link.__init__(self, kwargs.pop('name', 'correlation_summary'))

        # process arguments
        self._process_kwargs(kwargs, read_key='', store_key='', results_path='', methods=ALL_CORRS, pages_key='')
        self.check_extra_kwargs(kwargs)

    def initialize(self):
        """Initialize CorrelationSummary"""

        # check input arguments
        self.check_arg_types(read_key=str, store_key=str, results_path=str, methods=list, pages_key=str)
        self.check_arg_vals('read_key')

        # get I/O configuration
        io_conf = ProcessManager().service(ConfigObject).io_conf()

        # read report templates
        with open(persistence.io_path('templates', io_conf, 'df_summary_report.tex')) as templ_file:
            self.report_template = templ_file.read()
        with open(persistence.io_path('templates', io_conf, 'df_summary_report_page.tex')) as templ_file:
            self.page_template = templ_file.read()

        # get path to results directory
        if not self.results_path:
            self.results_path = persistence.io_path('results_data', io_conf, 'report')

        # check if output directory exists
        if os.path.exists(self.results_path):
            # check if path is a directory
            if not os.path.isdir(self.results_path):
                self.log().critical('output path "%s" is not a directory', self.results_path)
                raise AssertionError('output path is not a directory')
        else:
            # create directory
            self.log().debug('Making output directory "%s"', self.results_path)
            os.makedirs(self.results_path)

        # check methods
        for method in self.methods:
            if method not in ALL_CORRS:
                logstring = '"{}" is not a valid correlation method, please use one of {}'
                logstring = logstring.format(method, ', '.join(['"' + m + '"' for m in ALL_CORRS]))
                raise AssertionError(logstring)

        # initialize attributes
        self.pages = []

        return StatusCode.Success

    def execute(self):
        """Execute CorrelationSummary"""

        ds = ProcessManager().service(DataStore)

        import matplotlib.pyplot as plt
        from matplotlib import colors

        # fetch and check input data frame
        # drop all-nan columns right away
        df = ds.get(self.read_key, None).dropna(how='all', axis=1)
        if not isinstance(df, pd.DataFrame):
            self.log().critical('no Pandas data frame "%s" found in data store for %s', self.read_key, str(self))
            raise RuntimeError('no input data found for %s' % str(self))
        n_df = len(df.index)
        assert n_df, 'Pandas data frame "%s" frame has zero length' % self.read_key

        # create report pages
        if self.pages_key:
            self.pages = ds.get(self.pages_key, [])
            assert isinstance(self.pages, list), 'Pages key %s does not refer to a list' % self.pages_key

        # below, create report pages
        # for each correlation create resulting heatmap
        cors_list = []

        for method in self.methods:
            # compute correlations between all numerical variables
            self.log().debug('Computing "%s" correlations of dataframe "%s"', method, self.read_key)

            # mutual info, from sklearn
            if method == 'mutual_information':
                # numerical columns only
                cols = df.select_dtypes(include=[np.number]).columns

                # initialize correlation matrix
                n = len(cols)
                cors = np.zeros((n, n))
                for i, c in enumerate(cols):
                    # compare each column to all of the columns
                    cors[i, :] = mutual_info_regression(df[cols], df[c])

                cors = pd.DataFrame(cors, columns=cols, index=cols)

            elif method == 'correlation_ratio':
                # numerical columns only
                cols = df.select_dtypes(include=[np.number]).columns

                # choose bins for each column
                bins = {c: len(np.histogram(df[c])[1]) for c in cols}

                # sort rows into bins
                for c in cols:
                    df[str(c) + '_bin'] = pd.cut(df[c], bins[c])

                # initialize correlation matrix
                n = len(cols)
                cors = np.zeros((n, n))

                for i, x in enumerate(cols):
                    # definition from Wikipedia "correlation ratio"
                    xbin = str(x) + '_bin'
                    y_given_x = (df.groupby(xbin))[cols]
                    weighted_var_y_bar = (y_given_x.count() * (y_given_x.mean() - df.mean()) ** 2).sum()
                    weighted_var_y = df[cols].count() * df[cols].var()
                    cors[i, :] = weighted_var_y_bar / weighted_var_y

                cors = pd.DataFrame(cors, columns=cols, index=cols)

            else:
                cors = df.corr(method=method)
                cols = list(cors.columns)

            # replace column names with indices, as with numpy matrix, for plotting function below
            n = len(cols)
            cors.columns = range(n)

            # keep for potential later usage
            cors_list.append(cors)

            # plot settings
            title = '{0:s} correlation matrix'.format(method.capitalize())
            vmin = -1 if method in LINEAR_CORRS else 0
            vmax = 1
            color_map = 'RdYlGn' if method in LINEAR_CORRS else 'YlGn'
            fname = '_'.join(['correlations', self.read_key.replace(' ', ''), method]) + '.pdf'
            fpath = os.path.join(self.results_path, fname)

            # create nice looking plot
            self.log().debug('Saving correlation heatmap as {}'.format(fpath))
            visualization.vis_utils.plot_correlation_matrix(cors, cols, cols, fpath, title, vmin, vmax, color_map)

            # statistics table for report page
            n_unique = (n * n - n) / 2 if method is not 'correlation_ratio' else n * n
            stats = [('entries', n_df), ('bins', n * n), ('unique', n_unique),
                     ('> 0', (cors.values.ravel() > 0).sum()),
                     ('< 0', (cors.values.ravel() < 0).sum()),
                     ('avg', np.average(cors.values.ravel())),
                     ('max', max(cors.values.ravel())),
                     ('min', min(cors.values.ravel()))] if n > 0 else []
            stats_table = tabulate.tabulate(stats, tablefmt='latex')

            # add plot and table as page to report
            self.pages.append(self.page_template.replace('VAR_LABEL', title)
                              .replace('VAR_STATS_TABLE', stats_table)
                              .replace('VAR_HISTOGRAM_PATH', fpath))

        # save correlations to datastore if requested
        if self.store_key:
            ds[self.store_key] = cors_list
        if self.pages_key:
            ds[self.pages_key] = self.pages

        return StatusCode.Success

    def finalize(self):
        """Finalize CorrelationSummary"""

        # write report file
        with open('{}/report.tex'.format(self.results_path), 'w') as report_file:
            report_file.write(
                self.report_template.replace(
                    'INPUT_PAGES', ''.join(
                        self.pages)))

        return StatusCode.Success
