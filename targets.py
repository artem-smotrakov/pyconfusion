#!/usr/bin/python

import os
import core
from core import *
from enum import Enum

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
    start = s.find(first)
    end = s.find(second, start + 1)
    if start >= 0 and end > start:
        return s[start + 1:end].strip()
    return None

def read_file(filename):
    with open(filename) as f:
        return f.readlines()

class CTargetFinder:

    def __init__(self, path):
        self.path = path

    def run(self):
        targets = []
        for filename in look_for_c_files(self.path):
            for target in self.parse_c_file(filename):
                targets.append(target)

        return targets

    def parse_c_file(self, filename):
        self.log('parse file: ' + filename)
        targets = []

        content = read_file(filename)
        self.look_for_modules(content)

        return targets

    def look_for_modules(self, content):
        self.modules = {}
        for line in content:
            if 'PyModule_Create' in line:
                # extract variable name
                variable = extract(line, '*', '=')
                if variable == None:
                    self.warn('could not extract module variable name: ' + line)
                    continue
                # extract pointer to module structure
                pointer = extract(line, '&', ')')
                if pointer == None:
                    self.warn('could not extract pointer to module structure: ' + line)
                    continue
                # look for module name
                module_name = self.look_for_module_name(content, pointer)
                if module_name == None:
                    self.warn('could not find module name for pointer: ' + pointer)
                    continue
                self.log('found module: {0:s} (variable: {1:s})'.format(module_name, variable))
                self.modules[variable] = module_name

    def look_for_module_name(self, content, pointer):
        found_structure = False
        skipped_lines = 0
        for line in content:
            if skipped_lines == 1:
                return extract(line, '"', '"')
            if found_structure:
                skipped_lines = skipped_lines + 1
            if 'PyModuleDef' in line and pointer in line:
                found_structure = True

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

    def run(self):
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
