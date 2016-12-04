#!/usr/bin/python

import argparse
import core

# TODO: look for clinic sections
# TODO: extract function names from clinic sections
# TODO: extract number of arguments from clinic sections
# TODO: extract classes and method names from clinic sections
# TODO: generate and run Python code with extracted functions
# TODO: detect crashes
# TODO: detect and report wrong syntax
# TODO: add fuzzers for different types of function parameters

parser = argparse.ArgumentParser()
parser.add_argument('--src',  help='path to sources', default='./')
parser.add_argument('--mode', help='what do you want to do?', choices=['targets'], default='targets')

# create task
task = core.Task(parser.parse_args())
task.run()
