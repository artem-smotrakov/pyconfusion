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

def extract_func_name(line):
    tmp = line.split(',')
    if tmp == None or len(tmp) == 0:
        return None
    return extract(tmp[0], '"', '"')

def browse(module, name):
    loc = {}
    code = """
import {0:s}
result = dir({1:s})
""".format(module, name)
    exec(code, {}, loc)
    return loc['result']

def is_module(parent_module, module):
    loc = {}
    fullname = parent_module + '.' + module
    code = """
result = False
try:
    import {0}
    try:
        import inspect
        result = inspect.ismodule({1})
    except:
        try:
            from types import ModuleType
            result = isinstance({2}, ModuleType)
        except: pass
except: pass
""".format(parent_module, fullname, fullname)
    exec(code, {}, loc)
    return loc['result']

def is_class(module, name):
    loc = {}
    fullname = module + '.' + name
    code = """
result = False
try:
    import {0}
    try:
        import inspect
        result = inspect.isclass({1})
    except:
        try:
            result = isinstance({2}, type)
        except: pass
except: pass
""".format(module, fullname, fullname)
    exec(code, {}, loc)
    return loc['result']

def is_function(module, name):
    loc = {}
    fullname = fullname = module + '.' + name
    code = """
result = False
try:
    import {0}
    try:
        result = callable({1})
    except: pass
except: pass
""".format(module, fullname)
    exec(code, {}, loc)
    return loc['result']

def is_method(module, classname, name):
    loc = {}
    fullname = fullname = module + '.' + classname + '.' + name
    code = """
result = False
try:
    import {0}
    try:
        import inspect
        result = inspect.ismethod({1})
    except:
        try:
            result = callable({2})
        except: pass
except: pass
""".format(module, fullname, fullname)
    exec(code, {}, loc)
    return loc['result']

def get_signature(module, name):
    loc = {}
    fullname = module + '.' + name
    code = """
signature = None
try:
    import {0}
    import inspect
    signature = inspect.signature({1})
except: pass
""".format(module, fullname)
    exec(code, {}, loc)
    return loc['signature']

class CTargetFinder:

    def __init__(self, path):
        self.path = path

    def run(self, filter):
        # TODO: look for classes and methods
        self.warn('CTargetFinder looks only for functions in native modules')
        self.contents = {}

        for filename in look_for_c_files(self.path):
            self.contents[filename] = read_file(filename)

        self.classes = []
        self.targets = []
        self.native_modules = []
        for filename in self.contents:
            if not filter in filename:
                self.log('skip ' + filename)
                continue
            self.parse_c_file(filename)

        return self.targets

    def parse_c_file(self, filename):
        self.log('parse file: ' + filename)
        self.look_for_native_modules(filename)

    def look_for_native_modules(self, filename):
        content = self.contents[filename]
        for line in content:
            if 'PyModule_Create' in line:
                # extract variable name
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
                self.log('found module: {0:s}'.format(module_name))
                self.native_modules.append(module_name)
                self.look_for_targets(filename, module_name)

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

    def look_for_targets(self, filename, module):
        try:
            __import__(module)
        except ModuleNotFoundError as err:
            self.warn('{0}'.format(err))
            return
        for item in browse(module, module):
            if is_module(module, item):         self.add_module(filename, module, item)
            elif is_class(module, item):        self.add_class(filename, module, item)
            elif is_function(module, item):     self.add_function(filename, module, item)
            else: self.warn('unknown item: ' + item)

    def add_module(self, filename, parent_module, module):
        self.log('found module: ' + module)

    def add_class(self, filename, module, classname):
        self.log('found class: ' + classname)
        clazz = TargetClass(filename, module, classname)
        self.classes.append(clazz)

    def add_function(self, filename, module, func_name):
        func = TargetFunction(filename, module, func_name)
        # TODO: can we figure out parameter types here?
        # TODO: deprecate ParameterType
        # TODO: try to use __text_signature__ attribute if get_signature() fails
        signature = get_signature(module, func_name)
        if signature:
            func.no_unknown_parameters()
            for param in signature.parameters:
                func.add_parameter(ParameterType.any_object, signature.parameters[param].default)
        else: self.warn('could not get a signature of function: ' + func_name)
        self.targets.append(func)
        if func.has_unknown_parameters():   self.log('found function with unknown parameters: ' + func_name)
        elif func.has_no_parameters():      self.log('found function with no parameters: ' + func_name)
        else:                               self.log('found function with {0:d} parameters: {1:s}'.format(func.number_of_parameters(), func_name))

    # DEPRECATED
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
                    func_name = extract_func_name(line)
                    no_args = 'METH_NOARGS' in line
                else:
                    for define_line in self.look_for_define(line):
                        if func_name == None: func_name = extract_func_name(define_line)
                        if not no_args: no_args = 'METH_NOARGS' in define_line
                if func_name == None:
                    self.warn('could not extract function name: ' + line)
                    continue
                if no_args:
                    self.log('found a function with no arguments, skip it: ' + func_name)
                    continue
                self.log('found function: {0:s} with unknown parameters'.format(func_name))
                self.targets.append(TargetFunction(filename, module, func_name))
            if 'PyMethodDef' in line and methods_pointer in line:
                found_structure = True

    # DEPRECATED
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

# DEPRECATED
class ClinicParserState(Enum):
    expect_clinic_input = 1
    inside_clinic_input = 2
    expect_end_generated_code = 3

# DEPRECATED
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
                            current_method_or_function.no_unknown_parameters()
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
