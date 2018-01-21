#!/usr/bin/python

import argparse
import os.path
from fuzzer import *
from targets import *


def parse_list(filename):
    items = []
    with open(filename, encoding='utf-8', errors='ignore') as f:
        for line in f.readlines():
            line = line.strip()
            if len(line) == 0 or line.startswith('#'):
                continue
            for s in line.split(','):
                items.append(s.strip())
    return items


# contains fuzzer configuration
# all parameters can be accessed as attributes
class Task:

    # read arguments returned by argparse.ArgumentParser
    def __init__(self, args):
        self.args = vars(args)

    def command(self):  return self.args['command']
    def out(self):      return self.args['out']
    def finder_filter(self): return self.args['finder_filter']
    def fuzzer_filter(self): return self.args['fuzzer_filter']
    def fuzzing_data(self):  return self.args['fuzzing_data']

    # returns a list of excluded elements
    def excludes(self):
        if not self.args['exclude']:
            return []
        if os.path.isfile(self.args['exclude']):
            return parse_list(self.args['exclude'])
        return self.args['exclude'].split(',')

    # returns a list of modules
    def modules(self):
        if not self.args['modules']:
            return []
        if os.path.isfile(self.args['modules']):
            return parse_list(self.args['modules'])
        return self.args['modules'].split(',')

    def run(self):
        if   self.command() == 'targets': self.search_targets()
        elif self.command() == 'fuzzer':  self.fuzz()
        else: raise Exception('Unknown command: ' + self.command())

    def search_targets(self):
        return TargetFinder(self.args['src'], self.modules(), self.excludes()).run(self.finder_filter())

    def fuzz(self):
        targets = self.search_targets()
        if len(targets) == 0:
            self.warn('no targets! exiting ...')
            return
        extra_fuzzing_values = self.look_for_class_instances(targets)
        for target in targets:
            # check if the line matches specified filter
            if self.skip_fuzzing(target): continue

            if isinstance(target, TargetFunction):
                fuzzer = SmartFunctionFuzzer(target)
            elif isinstance(target, TargetClass):
                fuzzer = SmartClassFuzzer(target)
            else: raise Exception('Unknown target: {0}'.format(target))

            fuzzer.set_output_path(self.out())
            fuzzer.set_excludes(self.excludes())
            fuzzer.add_fuzzing_values(extra_fuzzing_values)
            fuzzer.add_general_parameter_values(extra_fuzzing_values)
            fuzzer.run()

    def look_for_class_instances(self, targets):
        self.log('look for extra fuzzing values')
        values = []
        for target in targets:
            if isinstance(target, TargetClass):
                self.log('try to create an instance of class: {0:s}'.format(target.name))
                if not target.has_constructor():
                    self.warn('could not find a constructor of class: {0}'.format(target.name))
                    continue
                fuzzer = CorrectParametersFuzzer(ConstructorCaller(target))
                fuzzer.set_output_path(self.out())
                fuzzer.run()
                if not fuzzer.success():
                    self.warn('could not create an instance of "{0:s}" class, skip fuzzing'. format(target.name))
                    continue
                constructor_caller = fuzzer.get_caller()
                self.log('found a new fuzzing value: class {0:s}'.format(target.name))
                values.append(constructor_caller.get_fuzzing_value())
        self.log('found {0:d} extra fuzzing values'.format(len(values)))
        return values

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

    def log(self, message):
        core.print_with_prefix('Task', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

parser = argparse.ArgumentParser()
parser.add_argument('--src',            help='path to sources', default='./')
parser.add_argument('--command',        help='what do you want to do?',
                    choices=['targets', 'fuzzer'], default='targets')
parser.add_argument('--fuzzer_filter',  help='target filter for fuzzer', default='')
parser.add_argument('--finder_filter',  help='file filter for finder', default='')
parser.add_argument('--out',            help='path to directory for generated tests')
parser.add_argument('--exclude',        help='comma-separated list of objects to exclude or path to exclude list', default='')
parser.add_argument('--modules',        help='comma-separated list of modules to fuzz or path to file with modules', default='')
parser.add_argument('--fuzzing_data',   help='a script which provides data for fuzzing', default='')

# create task
task = Task(parser.parse_args())
task.run()

Stats.get().print()
