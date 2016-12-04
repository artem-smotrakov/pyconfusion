#!/usr/bin/python

import argparse
import core

# TODO: detect and report wrong syntax
# TODO: add fuzzers for different types of function parameters

parser = argparse.ArgumentParser()
parser.add_argument('--src',  help='path to sources', default='./')
parser.add_argument('--mode', help='what do you want to do?', choices=['targets', 'fuzzer'], default='targets')
parser.add_argument('--filter',  help='target filter for fuzzer', default='')

# create task
task = core.Task(parser.parse_args())
task.run()
