#!/usr/bin/python

import argparse
import core

from fuzzer import FunctionFuzzer
from fuzzer import ClassFuzzer
from core import *
from targets import *

# contains fuzzer configuration
# all parameters can be accessed as attributes
class Task:

    # read arguments returned by argparse.ArgumentParser
    def __init__(self, args):
        self.args = vars(args)
        self.excludes = None
        if self.args['exclude']:
            self.excludes = self.args['exclude'].split(',')

    def __getattr__(self, name):
        return self.args[name]

    def run(self):
        if self.args['command'] == 'targets':
            self.search_targets()
        elif self.args['command'] == 'fuzzer':
            targets = self.search_targets()
            self.fuzz(targets)
        else:
            raise Exception('Unknown command: ' + self.args['command'])

    def search_targets(self):
        if self.args['src'] == None:
            raise Exception('Sources not specified')
        if self.args['finder'] == 'clinic':
            finder = ClinicTargetFinder(self.args['src'])
        elif self.args['finder'] == 'c':
            finder = CTargetFinder(self.args['src'])
        else:
            raise Exception('Unexpected finder type: ' + self.args['finder'])
        return finder.run(self.args['finder_filter'])

    def fuzz(self, targets):
        for target in targets:
            # check if the line matches specified filter
            if self.skip(target): continue

            if isinstance(target, TargetFunction):
                FunctionFuzzer(target, self.args['out']).run(self.args['mode'])

            if isinstance(target, TargetClass):
                ClassFuzzer(target, self.args['out'], self.excludes).run(self.args['mode'])

    def skip(self, target):
        # check if filter was specified
        if self.args['fuzzer_filter'] and not self.args['fuzzer_filter'] in target.fullname():
            return True

        if self.excludes:
            if isinstance(self.excludes, list):
                for exclude in self.excludes:
                    if exclude in target.fullname():
                        return True
            else:
                if self.excludes in target.fullname():
                    return True

        return False

parser = argparse.ArgumentParser()
parser.add_argument('--src',  help='path to sources', default='./')
parser.add_argument('--command', help='what do you want to do?', choices=['targets', 'fuzzer'], default='targets')
parser.add_argument('--finder', help='type of parser of C files', choices=['clinic', 'c'], default='clinic')
parser.add_argument('--mode', help='how do you want to do?', choices=['light', 'hard'], default='light')
parser.add_argument('--fuzzer_filter',  help='target filter for fuzzer', default='')
parser.add_argument('--finder_filter',  help='file filter for finder', default='')
parser.add_argument('--out', help='path to directory for generated tests')
parser.add_argument('--exclude', help='what do you want to exclude?')

# create task
task = Task(parser.parse_args())
task.run()

Stats.get().print()
