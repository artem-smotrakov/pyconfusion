#!/usr/bin/python

import argparse
import core

from fuzzer import LightFunctionFuzzer, HardFunctionFuzzer, SmartFunctionFuzzer
from fuzzer import ClassFuzzer
from core import *
from targets import *

# contains fuzzer configuration
# all parameters can be accessed as attributes
class Task:

    # read arguments returned by argparse.ArgumentParser
    def __init__(self, args):
        self.args = vars(args)
        self.excludes = []
        if self.args['exclude']:
            self.excludes = self.args['exclude'].split(',')

    def command(self):  return self.args['command']
    def src(self):      return self.args['src']
    def no_src(self):   return self.src() == None
    def mode(self):     return self.args['mode']
    def is_light(self): return self.mode() == 'light'
    def is_hard(self):  return self.mode() == 'hard'
    def out(self):      return self.args['out']
    def finder_filter(self): return self.args['finder_filter']
    def fuzzer_filter(self): return self.args['fuzzer_filter']
    def max_params(self):    return self.args['max_params']

    def run(self):
        if   self.no_src() == None: raise Exception('Sources not specified')
        if   self.command() == 'clinic_targets':  self.search_clinic_targets()
        elif self.command() == 'c_targets':     self.search_c_targets()
        elif self.command() == 'clinic_fuzzer': self.fuzz_clinic()
        elif self.command() == 'c_fuzzer':      self.fuzz_c()
        else: raise Exception('Unknown command: ' + self.command())

    def search_clinic_targets(self):
        return ClinicTargetFinder(self.src()).run(self.finder_filter())

    def search_c_targets(self):
        return CTargetFinder(self.src()).run(self.finder_filter())

    def fuzz_c(self):
        for target in self.search_c_targets():
            # check if the line matches specified filter
            if self.skip_fuzzing(target): continue

            if isinstance(target, TargetFunction):
                SmartFunctionFuzzer(target, self.out()).run()
            # TODO: support class fuzzing

    def fuzz_clinic(self):
        for target in self.search_clinic_targets():
            # check if the line matches specified filter
            if self.skip_fuzzing(target): continue

            if isinstance(target, TargetFunction):
                if self.is_light(): LightFunctionFuzzer(target, self.out()).run()
                if self.is_hard():  HardFunctionFuzzer(target, self.out()).run()

            if isinstance(target, TargetClass):
                ClassFuzzer(target, self.out(), self.excludes).run(self.mode())

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
                    choices=['clinic_targets', 'clinic_fuzzer', 'c_targets', 'c_fuzzer'],
                    default='c_targets')
parser.add_argument('--mode',           help='how do you want to do?',
                    choices=['light', 'hard'], default='light')
parser.add_argument('--fuzzer_filter',  help='target filter for fuzzer', default='')
parser.add_argument('--finder_filter',  help='file filter for finder', default='')
parser.add_argument('--out',            help='path to directory for generated tests')
parser.add_argument('--exclude',        help='what do you want to exclude?')
parser.add_argument('--max_params',     help='max number of parameters to try',
                    type=int, default=3)

# create task
task = Task(parser.parse_args())
task.run()

Stats.get().print()
