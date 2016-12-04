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


class ParserState(Enum):
    expect_clinic_input = 1
    inside_clinic_input = 2
    expect_end_generated_code = 3

class TargetFinder:

    def __init__(self, path):
        self.path = path

    def run(self):
        targets = []
        for filename in self.look_for_c_files(self.path):
            for target in self.parse_c_file(filename):
                targets.append(target)

        return targets

    def look_for_c_files(self, path):
        result = []
        if os.path.isfile(path):
            result.append(path)
            return result

        for root, dirs, files in os.walk(path):
            for file in files:
                # TODO: should it look for .h files as well?
                if file.endswith(".c"):
                    filename = os.path.join(root, file)
                    result.append(filename)

        return result

    def parse_c_file(self, filename):
        self.log('parse file: ' + filename)
        with open(filename) as f:
            content = f.readlines()
            state = ParserState.expect_clinic_input
            module = None
            classes = {}
            functions = []
            current_method_or_function = None
            for line in content:
                # trim the line
                line = line.rstrip('\n')

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
                        self.log('found module: ' + module)
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
                            self.log('found method of class \'{0:s}\': {1:s}'.format(clazz.name, methodname))
                            current_method_or_function = clazz.add_method(methodname)
                        else:
                            # add a function
                            index = line.find(' ')
                            if index > 0:
                                name = line[:index]
                            else:
                                name = line

                            name = name.strip()
                            self.log('found function: ' + name)

                            current_method_or_function = TargetFunction(filename, module, name)
                            functions.append(current_method_or_function)

                    # assume that a line with description of a parameter looks like '    param: desctiption'
                    if line.startswith('    ') and ': ' in line:
                        if current_method_or_function == None:
                            self.log('error while parsing line: ' + line)
                            self.log('warning: no function or method found yet')
                        else:
                            parameter_type = self.extract_parameter_type(line)
                            current_method_or_function.add_parameter(parameter_type)

        # merge all found targets
        targets = []

        for func in functions:
            targets.append(func)

        for key in classes:
            targets.append(classes[key])

        return targets

    def extract_parameter_type(self, line):
        parameter_str = line.strip()
        index = parameter_str.find(':')
        if index <= 0: return ParameterType.unknown
        parameter_str = parameter_str[index+1:]
        index = parameter_str.find(' ')
        if index > 0:
            parameter_str = parameter_str[:index]
        parameter_str = parameter_str.strip()
        if parameter_str == 'Py_buffer':
            return ParameterType.byte_like_object
        if parameter_str == 'int':
            return ParameterType.integer
        if parameter_str == 'object':
            return ParameterType.any_object

        return ParameterType.unknown

    def log(self, message):
        print_with_prefix('TargetFinder', message)

class ParameterType(Enum):
    unknown = 'unknown'
    byte_like_object = 'byte-like object'
    integer = 'integer'
    any_object = 'object'

    def __str__(self):
        return self.value

class TargetFunction:

    def __init__(self, filename, module, name):
        self.filename = filename
        self.module = module
        self.name = name
        self.parameter_types = []

    def number_of_parameters(self):
        return len(self.parameter_types)

    def add_parameter(self, parameter_type):
        self.parameter_types.append(parameter_type)

    def fullname(self):
        return self.name

class TargetClass:

    def __init__(self, filename, module, name):
        self.filename = filename
        self.module = module
        self.name = name
        self.methods = {}

    def add_method(self, name):
        if name in self.methods:
            raise Exception('Method already exists: ' + name)

        method = TargetMethod(name)
        self.methods[name] = method

        return method

    def fullname(self):
        return self.name

class TargetMethod:

    def __init__(self, name):
        self. name = name
        self.parameter_types = []

    def number_of_parameters(self):
        return len(self.parameter_types)

    def add_parameter(self, parameter_type):
        self.parameter_types.append(parameter_type)

class FunctionFuzzer:

    def __init__(self, function):
        self.function = function

    def run(self):
        self.log('fuzz function: ' + self.function.name)
        self.log('sources: ' + self.function.filename)
        self.log('number of parameters: {0:d}'.format(self.function.number_of_parameters()))

        if self.function.number_of_parameters() == 0:
            self.log('function doesn\'t have parameters, skip')
            return

        # TODO: add a command line option to specify excluded targets
        #       (os, and signal.pthread_kill should be excluded by default)
        if self.function.module == 'os':
            self.log('skip \'os\' module')
            return

        if self.function.name == 'signal.pthread_kill':
            self.log('skip \'signal.pthread_kill()\' function')
            return

        code = 'import ' + self.function.module + '\n'
        parameters = ''
        arg_number = 1
        parameter_str = ''
        for parameter_type in self.function.parameter_types:
            parameter_str += str(parameter_type) + ', '
            parameter_name = 'arg' + str(arg_number)
            value = self.default_value(parameter_type)
            code += '{0:s} = {1:s}\n'.format(parameter_name, value)
            if arg_number == self.function.number_of_parameters():
                parameters += parameter_name
            else:
                parameters += parameter_name + ', '
            arg_number = arg_number + 1

        code += '{0:s}({1:s})\n'.format(self.function.name, parameters)

        parameter_str = parameter_str.strip(', ')
        self.log('parameter types: ' + parameter_str)

        self.log('run the following code:\n\n' + code)

        try:
            exec(code)
        except TypeError as err:
            self.log('TypeError exception: {0}'.format(err))
        except NotADirectoryError as err:
            self.log('NotADirectoryError exception: {0}'.format(err))
        except OSError as err:
            self.log('OSError exception: {0}'.format(err))
        except ValueError as err:
            self.log('ValueError exception: {0}'.format(err))
        except AttributeError as err:
            self.log('warning: unexpected AttributeError exception: {0}'.format(err))
        except ModuleNotFoundError as err:
            self.log('warning: unexpected ModuleNotFoundError exception: {0}'.format(err))

    def log(self, message):
        print_with_prefix('FunctionFuzzer', message)

    def default_value(self, parameter_type):
        if parameter_type == ParameterType.byte_like_object:
            return 'bytes()'
        if parameter_type == ParameterType.integer:
            return '42'
        if parameter_type == ParameterType.any_object:
            # TODO: anything better?
            return '()'

        # TODO: anything better?
        return '()'
