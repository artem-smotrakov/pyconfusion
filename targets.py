#!/usr/bin/python

import os
import core
from core import *
from enum import Enum
from inspect import Parameter

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

def browse_module(module):
    loc = {}
    code = """
import {0:s}
result = dir({1:s})
""".format(module, module)
    exec(code, {}, loc)
    return loc['result']

def browse_in_module(module, name):
    loc = {}
    fullname = module + '.' + name
    code = """
import {0:s}
result = dir({1:s})
""".format(module, fullname)
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
        inspect_result = inspect.ismodule({1})
    except: pass
    try:
        from types import ModuleType
        isinstance_result = isinstance({2}, ModuleType)
    except: pass
    result = inspect_result or isinstance_result
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
        inspect_result = inspect.isclass({1})
    except: pass
    try:
        isinstance_result = isinstance({2}, type)
    except: pass
    result = inspect_result or isinstance_result
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
        inspect_result = inspect.ismethod({1})
    except: pass
    try:
        callable_result = callable({2})
    except: pass
    result = inspect_result or callable_result
except: pass
""".format(module, fullname, fullname)
    exec(code, {}, loc)
    return loc['result']

def get_signature(module, fullname):
    loc = {}
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

class TargetFinder:

    NO_SRC = 'no sources'

    def __init__(self, path, modules, excludes = []):
        self.path = path
        self.modules = modules
        self.excludes = excludes

    def run(self, filter):
        self.contents = {}
        self.classes = []
        self.targets = []
        self.native_modules = []

        if self.path:
            for filename in look_for_c_files(self.path):
                self.contents[filename] = read_file(filename)
            for filename in self.contents:
                if not filter in filename:
                    self.log('skip ' + filename)
                    continue
                self.parse_c_file(filename)

        if self.modules:
            for module in self.modules: self.look_for_targets(TargetFinder.NO_SRC, module)

        return self.targets

    def skip(self, target):
        if self.excludes:
            if isinstance(self.excludes, list):
                for exclude in self.excludes:
                    if exclude in target: return True
            else:
                if self.excludes in target: return True

        return False

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
        except:
            self.warn('could not import module: {0}'.format(module))
            return
        for item in browse_module(module):
            print('debug: ' + item)
            if self.skip(item):
                self.log('skip ' + item)
                return
            if item == 'True' or item == 'False': return
            elif is_module(module, item):       self.add_module(filename, module, item)
            elif is_class(module, item):        self.add_class(filename, module, item)
            elif is_function(module, item):     self.add_function(filename, module, item)
            else: self.warn('unknown item in module "{0:s}": {1:s}'.format(module, item))

    def add_module(self, filename, parent_module, module):
        # TODO: explore nested modules
        self.log('found module: ' + module)

    def add_class(self, filename, module, classname):
        self.log('found class: ' + classname)
        clazz = TargetClass(filename, module, classname)
        self.targets.append(clazz)
        for item in browse_in_module(module, classname):
            if is_method(module, classname, item): self.add_method(module, clazz, item)
            else: self.warn('unknown item in class "{0:s}": {1:s}'.format(classname, item))

    def add_method(self, module, clazz, method_name):
        method = TargetMethod(method_name, module, clazz)
        self.try_to_set_parameter_types(module, method)
        clazz.add_method(method)
        if method.has_unknown_parameters(): self.log('found a method with unknown parameters: ' + method.fullname())
        elif method.has_no_parameters():    self.log('found a method with no parameters: ' + method.fullname())
        else:                               self.log('found a method with {0:d} parameters: {1:s}'.format(method.number_of_parameters(), method.fullname()))

    def add_function(self, filename, module, func_name):
        func = TargetFunction(filename, module, func_name)
        # TODO: can we figure out parameter types here?
        self.try_to_set_parameter_types(module, func)
        self.targets.append(func)
        if func.has_unknown_parameters():   self.log('found a function with unknown parameters: ' + func_name)
        elif func.has_no_parameters():      self.log('found a function with no parameters: ' + func_name)
        else:                               self.log('found a function with {0:d} parameters: {1:s}'.format(func.number_of_parameters(), func_name))

    def try_to_set_parameter_types(self, module, target_callable):
        # TODO: try to use __text_signature__ attribute if get_signature() fails
        signature = get_signature(module, target_callable.fullname())
        if signature:
            target_callable.no_unknown_parameters()
            for param in signature.parameters:
                if param == 'self': continue
                # TODO: how can we get info about args and kwargs?
                if param == 'args': continue
                if param == 'kwargs': continue
                if signature.parameters[param].default == Parameter.empty: default_value = None
                else: default_value = signature.parameters[param].default
                target_callable.add_parameter(ParameterType.any_object, default_value)
        else: self.warn('could not get a signature: ' + target_callable.fullname())

    def log(self, message):
        print_with_prefix('TargetFinder', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))
