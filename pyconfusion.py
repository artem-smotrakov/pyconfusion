#!/usr/bin/python

import argparse
import core

from fuzzer import FunctionFuzzer
from core import *

# TODO: fuzz one by one parameter (other parameters should contain valid types)
# TODO: gather info, and print out a summary in the end
# TODO: add fuzzers for different types of function parameters

# contains fuzzer configuration
# all parameters can be accessed as attributes
class Task:

    # read arguments returned by argparse.ArgumentParser
    def __init__(self, args):
        self.args = vars(args)

    def __getattr__(self, name):
        return self.args[name]

    def run(self):
        if self.args['mode'] == 'targets':
            self.search_targets()
        elif self.args['mode'] == 'fuzzer':
            targets = self.search_targets()
            self.fuzz(targets)
        else:
            raise Exception('Unknown mode: ' + self.args['mode'])

    def search_targets(self):
        if self.args['src'] == None:
            raise Exception('Sources not specified')
        finder = TargetFinder(self.args['src'])
        return finder.run()

    def fuzz(self, targets):
        for target in targets:
            # check if the line matches specified filter
            if not self.match_filter(target): continue

            # TODO: support fuzzing methods
            if isinstance(target, TargetFunction):
                FunctionFuzzer(target).run()

    def match_filter(self, target):
        # check if filter was specified
        if self.args['filter'] == None or not self.args['filter']:
            return True

        return self.args['filter'] in target.fullname()

parser = argparse.ArgumentParser()
parser.add_argument('--src',  help='path to sources', default='./')
parser.add_argument('--mode', help='what do you want to do?', choices=['targets', 'fuzzer'], default='targets')
parser.add_argument('--filter',  help='target filter for fuzzer', default='')

# create task
task = Task(parser.parse_args())
task.run()
