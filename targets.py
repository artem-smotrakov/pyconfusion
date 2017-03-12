#!/usr/bin/python

import os
import core
from core import *
from enum import Enum
from difflib import SequenceMatcher

def look_for_c_files(path):
    result = []
    if os.path.isfile(path):
        result.append(path)
        return result

    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.c') or file.endswith('.h'):
                filename = os.path.join(root, file)
                result.append(filename)

    return result

def extract(s, first, second):
    start = 0
    if first != None:
        start = s.find(first)
    end = s.find(second, start + 1)
    if start >= 0 and end > start:
        return s[start + 1:end].strip()
    return None

def read_file(filename):
    with open(filename) as f:
        return f.readlines()

def contains_all(string, values=[]):
    for value in values:
        if not value in string:
            return False
    return True

def extract_fucn_name(line):
    tmp = line.split(',')
    if tmp == None or len(tmp) == 0:
        return None
    return extract(tmp[0], '"', '"')

class CTargetFinder:

    max_parameters_guess = 10
    parameter_guesses = ('42', '42.3', 'True', '\'ololo\'', 'bytes()', 'bytearray()', '()', '[]', '{}')

    def __init__(self, path):
        self.path = path

    def run(self, filter):
        targets = []
        self.contents = {}

        for filename in look_for_c_files(self.path):
            self.contents[filename] = read_file(filename)

        self.targets = []
        for filename in self.contents:
            if not filter in filename:
                self.log('skip ' + filename)
                continue
            self.parse_c_file(filename)

        return self.targets

    def parse_c_file(self, filename):
        self.log('parse file: ' + filename)
        self.look_for_modules(filename)

    def look_for_modules(self, filename):
        content = self.contents[filename]
        self.modules = {}
        for line in content:
            if 'PyModule_Create' in line:
                # extract variable name
                variable = extract(line, '*', '=')
                if variable == None:
                    variable = extract(line, None, '=')
                if variable == None:
                    self.warn('could not extract module variable name: ' + line)
                    continue
                # extract pointer to module structure
                pointer = extract(line, '&', ')')
                if pointer == None:
                    self.warn('could not extract pointer to module structure: ' + line)
                    continue
                # look for module name
                module_name = self.look_for_module_name(filename, pointer)
                if module_name == None:
                    self.warn('could not find module name for pointer: ' + pointer)
                    continue
                self.log('found module: {0:s} (variable: {1:s})'.format(module_name, variable))
                self.modules[variable] = module_name
                self.look_for_module_functions(filename, pointer, module_name)

    def look_for_module_name(self, filename, pointer):
        content = self.contents[filename]
        found_structure = False
        skipped_lines = 0
        for line in content:
            if skipped_lines == 1:
                return extract(line, '"', '"')
            if found_structure:
                skipped_lines = skipped_lines + 1
            if 'PyModuleDef' in line and pointer in line:
                found_structure = True

    def look_for_module_functions(self, filename, pointer, module):
        content = self.contents[filename]
        found_structure = False
        skipped_lines = 0
        methods_pointer = None
        for line in content:
            if skipped_lines == 4:
                methods_pointer = extract(line, None, ',')
                break
            if found_structure:
                skipped_lines = skipped_lines + 1
            if 'PyModuleDef' in line and pointer in line:
                found_structure = True
        if methods_pointer == None:
            self.warn('could not find methods pointer for module pointer: ' + pointer)
            return
        self.functions = []
        found_structure = False
        for line in content:
            if found_structure:
                line = line.strip();
                if '};' in line:
                    break
                func_name = None
                no_args = False
                if line.startswith('{'):
                    func_name = extract_fucn_name(line)
                    no_args = 'METH_NOARGS' in line
                else:
                    for define_line in self.look_for_define(line):
                        if func_name == None: func_name = extract_fucn_name(define_line)
                        if not no_args: no_args = 'METH_NOARGS' in define_line
                if func_name == None:
                    self.warn('could not extract function name: ' + line)
                    continue
                if no_args:
                    self.log('found a function with no arguments, skip it: ' + func_name)
                    continue
                func = TargetFunction(filename, module, func_name)
                self.guess_parameter_types(func)
                if func.has_unknown_parameters():
                    self.warn('could not figure out parameter types for ' + func_name)
                else:
                    self.log('found function: {0:s} with {1:d} parameters'.format(func_name, func.number_of_parameters()))
                    self.targets.append(func)
            if 'PyMethodDef' in line and methods_pointer in line:
                found_structure = True

    def guess_parameter_types(self, func):
        # check if invocation without parameters is successful
        caller = FunctionCaller(func)
        try:
            caller.call()
            # no exception, seems like the function have 0 parameters
            func.no_unknown_parameters()
            return
        except:
            pass
        number_of_params = 1
        exceptions = {}
        while number_of_params <= CTargetFinder.max_parameters_guess:
            exception = self.run_func_with_n_parameters(func, number_of_params)
            if exception == None:
                # no exception, seems like we figured out a number of parameters
                func.no_unknown_parameters()
                return
            elif isinstance(exception, NameError):
                self.warn('unexpected NameError, looks like something went wrong: {0}'.format(exception))
                return
            elif not isinstance(exception, TypeError):
                # TypeError is usually thrown in case of wrong parameter number
                # seems like we're good since it's not TypeError
                self.log('function has {0:d} parameters, got {1}'.format(number_of_params, exception))
                func.no_unknown_parameters()
                return
            exceptions[number_of_params] = '{0}'.format(exception)
            if number_of_params >= 3:
                n = self.look_for_different_exception(exceptions)
                if n != None:
                    # we found it
                    func.reset_parameter_types()
                    i = 0
                    while i < n:
                        func.add_parameter(ParameterType.any_object)
                        i = i + 1
                    func.no_unknown_parameters()
                    return
            number_of_params = number_of_params + 1

    def look_for_different_exception(self, exceptions):
        length = len(exceptions)
        similarity = {}
        similarity[length] = SequenceMatcher(None, exceptions[1], exceptions[len(exceptions)]).ratio()
        similarity[0] = similarity[length]
        s = similarity[length]
        i = 1
        while i < length:
            similarity[i] = SequenceMatcher(None, exceptions[i], exceptions[i+1]).ratio()
            s = s + similarity[i]
            i = i + 1
        avg = s / length
        i = 1
        index = -1
        while i < length:
            if similarity[i] < avg:
                index = i
                break
            i = i + 1
        if index < 0:
            # seems like the function has more parameters
            return None
        elif similarity[index+1] < avg:
            return index+1
        elif similarity[index-1] < avg:
            return index
        else:
            raise Exception('should not reach here')

    def run_func_with_n_parameters(self, func, number_of_params):
        func.reset_parameter_types()
        i = 0
        while i < number_of_params:
            func.add_parameter(ParameterType.any_object)
            i = i + 1
        caller = FunctionCaller(func)
        try:
            caller.call()
            return None
        except Exception as e:
            return e

    def look_for_define(self, string):
        for filename in self.contents:
            content = self.contents[filename]
            result = []
            for line in content:
                if len(result) > 0:
                    result.append(line)
                if len(result) > 0 and not '\\' in line:
                    return result
                if contains_all(line, ['#define', string]):
                    result.append(line)
                    if '\\' in line:
                        continue
                    else:
                        return result
            if len(result) > 0:
                return result

        return []

    def log(self, message):
        print_with_prefix('CTargetFinder', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class ClinicParserState(Enum):
    expect_clinic_input = 1
    inside_clinic_input = 2
    expect_end_generated_code = 3

class ClinicTargetFinder:

    def __init__(self, path):
        self.path = path

    def run(self, filter):
        if filter != None:
            self.log('filters are not supported')
        targets = []
        for filename in look_for_c_files(self.path):
            for target in self.parse_c_file(filename):
                targets.append(target)

        return targets

    def parse_c_file(self, filename):
        self.log('parse file: ' + filename)
        with open(filename) as f:
            content = f.readlines()
            state = ClinicParserState.expect_clinic_input
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
                    if state != ClinicParserState.expect_clinic_input:
                        raise Exception('Unexpected [clinic input] section')

                    state = ClinicParserState.inside_clinic_input
                    star_found = False
                    continue

                if '[clinic start generated code]' in line:
                    if state != ClinicParserState.inside_clinic_input:
                        raise Exception('Unexpected [clinic start generated code] section')

                    # now start skipping just skip the actual code
                    state = ClinicParserState.expect_end_generated_code
                    continue

                if '[clinic end generated code' in line:
                    # found [clinic end generated code] line
                    # then we look for next [clinic input] section
                    # we don't check for ClinicParserState.expect_end_generated_code state here
                    # because there may be multiple [clinic end generated code] sections

                    state = ClinicParserState.expect_clinic_input
                    continue

                # skip the code if we are in [clinic end generated code] section
                if state == ClinicParserState.expect_end_generated_code:
                    continue

                # check if we are inside [clinic input] section, and should expect declarations
                if state == ClinicParserState.inside_clinic_input:
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
                        self.log('warning: no module found, line: ' + line)
                        self.log('skip file')
                        return []

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
                            if '.' in name:
                                parts = name.split('.')
                                name = parts[len(parts)-1]
                            self.log('found function: ' + name)

                            current_method_or_function = TargetFunction(filename, module, name)
                            functions.append(current_method_or_function)

                    # stop if we found keywords
                    # TODO: try to fuzz keywords
                    if line.strip() == '*':
                        star_found = True

                    if star_found: continue

                    # assume that a line with description of a parameter looks like '  param: desctiption'
                    if line.startswith('  ') and ': ' in line:
                        if current_method_or_function == None:
                            self.log('error while parsing line: ' + line)
                            self.log('warning: no function or method found yet')
                        else:
                            index = line.find(':')
                            if index <= 0: continue
                            parameter_name = line[:index].strip()

                            # TODO: seems like we need to take into account indentation here
                            #       instead of looking for whitespaces
                            if ' ' in parameter_name: continue

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
        default_value = None
        if index >= 0:
            pstr = pstr[:index]
            pstr = pstr.strip()
            default_value = pstr[index+1:]
            default_value = default_value.strip()

        t = ParameterType.extract_parameter_type(pstr, default_value)
        if t == ParameterType.unknown:
            self.log('warning: unexpected type string: ' + pstr)

        return t

    def log(self, message):
        print_with_prefix('ClinicTargetFinder', message)
