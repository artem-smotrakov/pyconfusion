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
        self.excludes = []
        self.modules = []
        if self.args['exclude']:
            self.excludes = self.args['exclude'].split(',')
        if self.args['modules']:
            self.modules = self.args['modules'].split(',')

    def command(self):  return self.args['command']
    def src(self):      return self.args['src']
    def no_src(self):   return self.src() == None
    def out(self):      return self.args['out']
    def finder_filter(self): return self.args['finder_filter']
    def fuzzer_filter(self): return self.args['fuzzer_filter']

    def run(self):
        if   self.no_src() == None: raise Exception('Sources not specified')
        if   self.command() == 'targets': self.search_targets()
        elif self.command() == 'fuzzer':  self.fuzz()
        else: raise Exception('Unknown command: ' + self.command())

    def search_targets(self):
        return TargetFinder(self.src(), self.modules).run(self.finder_filter())

    def fuzz(self):
        for target in self.search_targets():
            # check if the line matches specified filter
            if self.skip_fuzzing(target): continue

            if isinstance(target, TargetFunction):
                SmartFunctionFuzzer(target, self.out()).run()
            if isinstance(target, TargetClass):
                SmartClassFuzzer(target, self.out(), self.excludes).run()

    def skip_fuzzing(self, target):
        # check if filter was specified
        if self.fuzzer_filter() and not self.fuzzer_filter() in target.fullname():
            return True

        if self.excludes:
            if isinstance(self.excludes, list):
                for exclude in self.excludes:
                    if exclude in target.fullname(): return True
            else:
                if self.excludes in target.fullname(): return True

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

# create task
task = Task(parser.parse_args())
task.run()

Stats.get().print()
