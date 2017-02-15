#!/usr/bin/python

import argparse
import datetime
import os
import time

parser = argparse.ArgumentParser()
parser.add_argument('--tests',  help='path to tests', default='.')
args = parser.parse_args()

start_time = time.time()
total_tests = 0

# find all .py files in specified directory, and run them with exec()
for root, dirs, files in os.walk(args.tests):
    for file in files:
        test = root + os.sep + file
        total_tests = total_tests + 1
        print('run {0:s}'.format(test))
        with open(test) as file:
            code = file.read()
            try:
                exec(code)
                print('wow, it succeded')
            except Exception as err:
                print('exception {0}: {1}'.format(type(err), err))

total_time = round(time.time() - start_time)
time_str = str(datetime.timedelta(seconds=total_time))

print('{0:d} tests are done'.format(total_tests))
print('Time: {0}'.format(time_str))
print('Game over')
