#!/usr/bin/python

import argparse
import core

from fuzzer     import *
from core       import *
from targets    import *

# contains fuzzer configuration
# all parameters can be accessed as attributes
class Task:

    # read arguments returned by argparse.ArgumentParser
    def __init__(self, args):
        self.args = vars(args)

    def command(self):  return self.args['command']
    def src(self):      return self.args['src']
    def no_src(self):   return self.src() == None
    def out(self):      return self.args['out']
    def finder_filter(self): return self.args['finder_filter']
    def fuzzer_filter(self): return self.args['fuzzer_filter']
    def fuzzing_data(self):  return self.args['fuzzing_data']

    def excludes(self):
        if self.args['exclude']:
            return self.args['exclude'].split(',')
        else:
            return []

    def modules(self):
        if self.args['modules']:
            return self.args['modules'].split(',')
        else:
            return []

    def run(self):
        if   self.no_src() == None: raise Exception('Sources not specified')
        if   self.command() == 'targets': self.search_targets()
        elif self.command() == 'fuzzer':  self.fuzz()
        else: raise Exception('Unknown command: ' + self.command())

    def search_targets(self):
        return TargetFinder(self.src(), self.modules(), self.excludes()).run(self.finder_filter())

    def fuzz(self):
        for target in self.search_targets():
            # check if the line matches specified filter
            if self.skip_fuzzing(target): continue

            if isinstance(target, TargetFunction):
                fuzzer = SmartFunctionFuzzer(target)
            elif isinstance(target, TargetClass):
                fuzzer = SmartClassFuzzer(target)
            else: raise Exception('Unknown target: {0}'.format(target))

            fuzzer.set_output_path(self.out())
            fuzzer.set_excludes(self.excludes())
            fuzzer.run()

    # returns true if fuzzing of specified target should be skipped
    def skip_fuzzing(self, target):
        # check if filter was specified
        if self.fuzzer_filter() and not self.fuzzer_filter() in target.fullname():
            return True

        if self.excludes():
            if isinstance(self.excludes(), list):
                for exclude in self.excludes():
                    if exclude in target.fullname(): return True
            else:
                if self.excludes() in target.fullname(): return True

        return False

parser = argparse.ArgumentParser()
parser.add_argument('--src',            help='path to sources', default='./')
parser.add_argument('--command',        help='what do you want to do?',
                    choices=['targets', 'fuzzer'], default='targets')
parser.add_argument('--fuzzer_filter',  help='target filter for fuzzer', default='')
parser.add_argument('--finder_filter',  help='file filter for finder', default='')
parser.add_argument('--out',            help='path to directory for generated tests')
parser.add_argument('--exclude',        help='what do you want to exclude?')
parser.add_argument('--modules',        help='list of modules to fuzz', default='')
parser.add_argument('--fuzzing_data',   help='a script which provides data for fuzzing', default='')

# create task
task = Task(parser.parse_args())
task.run()

Stats.get().print()
