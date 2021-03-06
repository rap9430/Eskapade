# ********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                 *
# * Macro  : esk603_read_csv_to_spark_df                                         *
# * Created: 2017/06/08                                                          *
# * Description:                                                                 *
# *     Tutorial macro for writing Spark data to a CSV file                      *
# *                                                                              *
# * Redistribution and use in source and binary forms, with or without           *
# * modification, are permitted according to the terms listed in the file        *
# * LICENSE.                                                                     *
# ********************************************************************************

from collections import OrderedDict as odict
import logging
log = logging.getLogger('macro.esk603_read_csv_to_spark_df')

from eskapade import ConfigObject, DataStore, ProcessManager
from eskapade.core import persistence
from eskapade.spark_analysis import SparkManager
from eskapade import spark_analysis

log.debug('Now parsing configuration file esk603_read_csv_to_spark_df')


##########################################################################
# --- minimal analysis information

proc_mgr = ProcessManager()

settings = proc_mgr.service(ConfigObject)
settings['analysisName'] = 'esk603_read_csv_to_spark_df'
settings['version'] = 0


##########################################################################
# --- start Spark session

spark = proc_mgr.service(SparkManager).create_session(eskapade_settings=settings)


##########################################################################
# --- CSV and data settings

output_dir = 'file:' + persistence.io_dir('results_data', settings.io_conf())
num_files = 1
separator = ','
write_header = True
columns = ['index', 'foo', 'bar']
rows = [(it, 'foo{:d}'.format(it), (it + 1) / 2.) for it in range(100)]


##########################################################################
# --- Spark data

ds = proc_mgr.service(DataStore)
ds['rdd'] = spark.sparkContext.parallelize(rows)
ds['df'] = spark.createDataFrame(ds['rdd'], schema=columns)


##########################################################################
# --- now set up the chains and links based on configuration flags

writers = odict()

# create generic data-frame-writer link
writers['df_generic_writer'] = spark_analysis.SparkDfWriter(name='df_generic_writer',
                                                            read_key='df',
                                                            write_methods=['csv'],
                                                            num_files=num_files)

# create generic RDD-writer link
writers['rdd_generic_writer'] = spark_analysis.SparkDfWriter(name='rdd_generic_writer',
                                                             read_key='rdd',
                                                             schema=columns,
                                                             write_methods=['csv'],
                                                             num_files=num_files)

# create RDD-CSV-writer link
writers['rdd_csv_writer'] = spark_analysis.SparkDataToCsv(name='rdd_csv_writer',
                                                          read_key='rdd',
                                                          output_path='{}/rdd_csv'.format(output_dir),
                                                          mode='overwrite',
                                                          sep=separator,
                                                          header=columns if write_header else False,
                                                          num_files=num_files)

# set generic-writer arguments
for input_format in ('df', 'rdd'):
    key = '{}_generic_writer'.format(input_format)
    writers[key].write_meth_args['csv'] = ('{0:s}/{1:s}_generic'.format(output_dir, input_format),)
    writers[key].write_meth_kwargs['csv'] = dict(sep=separator,
                                                 header=write_header,
                                                 mode='overwrite')

# add links to chain
chain = proc_mgr.add_chain('Write')
for lnk in writers.values():
    chain.add_link(lnk)


##########################################################################

log.debug('Done parsing configuration file esk603_read_csv_to_spark_df')
