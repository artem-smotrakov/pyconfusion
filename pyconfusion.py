#!/usr/bin/python

import argparse
import core

# TODO: before starting fuzzing, check if we can make a call that doesn't cause TypeError
#       otherwise, skip with a warning
# TODO: fuzz one by one parameter (other parameters should contain valid types)
# TODO: print a summary in the end
# TODO: add fuzzers for different types of function parameters

parser = argparse.ArgumentParser()
parser.add_argument('--src',  help='path to sources', default='./')
parser.add_argument('--mode', help='what do you want to do?', choices=['targets', 'fuzzer'], default='targets')
parser.add_argument('--filter',  help='target filter for fuzzer', default='')

# create task
task = core.Task(parser.parse_args())
task.run()
