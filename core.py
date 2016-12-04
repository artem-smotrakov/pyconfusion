#!/usr/bin/python

import textwrap
import os

from enum import Enum

# print out a message with prefix
def print_with_prefix(prefix, message):
    print('[{0:s}] {1}'.format(prefix, message))

# print out a message with specified prefix
def print_with_indent(prefix, first_message, other_messages):
    formatted_prefix = '[{0:s}] '.format(prefix)
    print('{0:s}{1}'.format(formatted_prefix, first_message))
    if len(other_messages) > 0:
        indent = ' ' * len(formatted_prefix)
        wrapper = textwrap.TextWrapper(
            initial_indent=indent, subsequent_indent=indent, width=80)
        for message in other_messages:
            print(wrapper.fill(message))

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
            if self.args['src'] == None:
                raise Exception('Sources not specified')
            finder = TargetFinder(self.args['src'])
            finder.run()
        else:
            raise Exception('Unknown mode: ' + self.args['mode'])

class ParserState(Enum):
    expect_clinic_input = 1
    inside_clinic_input = 2
    expect_end_generated_code = 3

class TargetFinder:

    def __init__(self, directory):
        self.directory = directory

    def run(self):
        targets = []
        for root, dirs, files in os.walk(self.directory):
            for file in files:
                # TODO: should it look for .h files as well?
                if file.endswith(".c"):
                    filename = os.path.join(root, file)
                    for target in self.parse_c_file(filename):
                        targets.append(target)

        return targets

    def parse_c_file(self, filename):
        self.log('parse ' + filename)
        with open(filename) as f:
            content = f.readlines()
            state = ParserState.expect_clinic_input
            module = None
            classes = {}
            functions = []
            for line in content:
                # trim the line
                line = line.strip()

                # skip empty lines
                if not line: continue

                # all function and method declarations go in [clinic input] section
                if '[clinic input]' in line:
                    if state != ParserState.expect_clinic_input:
                        raise Exception('Unexpected [clinic input] section')

                    state = ParserState.inside_clinic_input
                    continue

                if '[clinic start generated code]' in line:
                    if state != ParserState.inside_clinic_input:
                        raise Exception('Unexpected [clinic start generated code] section')

                    # now start skipping just skip the actual code
                    state = ParserState.expect_end_generated_code
                    continue

                if '[clinic end generated code' in line:
                    # found [clinic end generated code] line
                    # then we look for next [clinic input] section
                    # we don't check for ParserState.expect_end_generated_code state here
                    # because there may be multiple [clinic end generated code] sections

                    state = ParserState.expect_clinic_input
                    continue

                # skip the code if we are in [clinic end generated code] section
                if state == ParserState.expect_end_generated_code:
                    continue

                # check if we are inside [clinic input] section, and should expect declarations
                if state == ParserState.inside_clinic_input:
                    # parse [clinic input] section

                    # ignore comments
                    if line.startswith('#'): continue

                    # check if we found a module declaration
                    if line.startswith('module '):
                        # there should be only one module in a file
                        if module != None:
                            self.log('error while parsing line: ' + line)
                            raise Exception('Module already defined')

                        module = line[len('module'):]
                        module = module.strip()
                        self.log('found \'{0:s}\' module'.format(module))
                        continue

                     # at this point we should have found a module name
                    if module is None:
                        self.log('error while parsing line: ' + line)
                        raise Exception('No module name found')

                    # check if we found a class declaration
                    if line.startswith('class '):
                        classname = line[len('class '):]
                        classname = classname[:classname.index(' ')]
                        classname = classname.strip();

                        # check for duplicate class declarations
                        if classname in classes:
                            self.log('error while parsing line: ' + line)
                            raise Exception('duplicate class declaration')

                        self.log('found class ' + classname)

                        clazz = TargetClass(filename, module, classname)
                        classes[classname] = clazz
                        continue

                    if line.startswith(module):
                        # check if it's a method of a class
                        clazz = None
                        for classname in classes:
                            if line.startswith(classname):
                                # it is a declaration of a method
                                clazz = classes[classname];
                                break

                        if clazz != None:
                            # add a method
                            methodname = line[len(clazz.name)+1:]
                            self.log('found method ' + methodname)
                            clazz.add_method(methodname)
                        else:
                            # add a function
                            self.log('found function ' + line)
                            functions.append(TargetFunction(filename, module, line))

        # merge all found targets
        targets = []

        for func in functions:
            targets.append(func)

        for key in classes:
            targets.append(classes[key])

        return targets

    def log(self, message):
        print_with_prefix('TargetFinder', message)

class TargetFunction:

    def __init__(self, filename, module, name):
        self.filename = filename
        self.module = module
        self.name = name

class TargetClass:

    def __init__(self, filename, module, name):
        self.filename = filename
        self.module = module
        self.name = name
        self.methods = {}

    def add_method(self, name):
        if name in self.methods:
            raise Exception('Method already exists: ' + name)

        self.methods[name] = TargetMethod(name)

class TargetMethod:

    def __init__(self, name):
        self. name = name
