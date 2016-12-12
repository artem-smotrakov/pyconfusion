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
        pstr = line.strip()
        index = pstr.find(':')
        if index <= 0: return ParameterType.unknown
        pstr = pstr[index+1:]
        index = pstr.find(' ')
        if index > 0:
            pstr = pstr[:index]
        pstr = pstr.strip()

        # check if there is a default value
        # TODO: use default value while fuzzing
        index = pstr.rfind('=')
        if index >= 0:
            pstr = pstr[:index]
            pstr = pstr.strip()

        if pstr == 'Py_buffer':
            return ParameterType.byte_like_object
        if pstr == 'int':
            return ParameterType.integer
        if pstr == 'long':
            return ParameterType.long
        if pstr == 'double':
            return ParameterType.double
        if pstr == 'Py_complex_protected' or pstr == 'Py_complex':
            return ParameterType.complex_number
        if pstr == 'object' or 'object(c_default=' in pstr:
            return ParameterType.any_object
        if pstr == 'Py_ssize_t':
            return ParameterType.ssize_t
        if pstr == 'int(c_default="0")' or pstr == 'int(c_default="1")':
            return ParameterType.boolean
        if pstr.startswith('str(accept='):
            return ParameterType.string
        if pstr == 'ascii_buffer':
            return ParameterType.ascii_buffer
        if pstr == 'unicode':
            return ParameterType.unicode_buffer
        if 'unsigned_int' in pstr:
            return ParameterType.unsigned_int
        if 'lzma_filter' in pstr:
            return ParameterType.lzma_filter
        if 'lzma_vli' in pstr:
            return ParameterType.lzma_vli

        return ParameterType.unknown

    def log(self, message):
        print_with_prefix('TargetFinder', message)

class ParameterType(Enum):
    unknown = 'unknown'
    byte_like_object = 'byte-like object'
    integer = 'integer'
    long = 'long'
    any_object = 'object'
    ssize_t = 'ssize_t'
    double = 'double'
    boolean = 'boolean'
    string = 'string'
    ascii_buffer = 'ascii buffer'
    unicode_buffer = 'unicode buffer'
    unsigned_int = 'unsigned integer'
    complex_number = 'complex number'
    lzma_filter = 'lzma_filter'
    lzma_vli = 'lzma_vli'

    def __str__(self):
        return self.value

    def default_value(ptype):
        if ptype == ParameterType.byte_like_object:
            return 'bytes()'
        if ptype == ParameterType.integer:
            return '1'
        if ptype == ParameterType.unsigned_int:
            return '1'
        if ptype == ParameterType.long:
            return '1'
        if ptype == ParameterType.complex_number:
            return 'complex(1.0, -1.0)'
        if ptype == ParameterType.any_object:
            # TODO: anything better?
            return '()'
        if ptype == ParameterType.ssize_t:
            return '1'
        if ptype == ParameterType.double:
            return '4.2'
        if ptype == ParameterType.boolean:
            return 'True'
        if ptype == 'string':
            return '\'string\''
        if ptype == ParameterType.ascii_buffer:
            return '\'ascii\''
        if ptype == ParameterType.unicode_buffer:
            return '\'unicode\''
        if ptype == ParameterType.lzma_filter:
            # TODO: anything better?
            return '()'
        if ptype == ParameterType.lzma_vli:
            # TODO: anything better?
            return '()'

        # TODO: anything better?
        return '()'

class FunctionCaller:

    def __init__(self, function):
        self.function = function
        self.parameter_values = []
        for parameter_type in function.parameter_types:
            self.parameter_values.append(ParameterType.default_value(parameter_type))
        self.prepare()

    def prepare(self):
        if self.function.number_of_parameters() != len(self.parameter_values):
            raise Exception('number of parameters is not equal to number of values')

        self.code = 'import ' + self.function.module + '\n'
        parameters = ''
        arg_number = 1
        for parameter_type in self.function.parameter_types:
            parameter_name = 'p' + str(arg_number)
            value = self.parameter_values[arg_number-1]
            self.code += '{0:s} = {1:s}\n'.format(parameter_name, value)
            if arg_number == self.function.number_of_parameters():
                parameters += parameter_name
            else:
                parameters += parameter_name + ', '
            arg_number = arg_number + 1

        self.code += '{0:s}({1:s})\n'.format(self.function.name, parameters)

    def set_parameter_value(self, arg_number, value):
        self.parameter_values[arg_number - 1] = value
        self.prepare()

    def call(self):
        self.log('run the following code:\n\n' + self.code)
        exec(self.code)

    def log(self, message):
        print_with_prefix('FunctionCaller', message)

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
