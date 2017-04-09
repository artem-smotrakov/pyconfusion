#!/usr/bin/python

import datetime
import textwrap
import time
import os

from enum import Enum
from string import Template

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

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class Stats(metaclass=Singleton):

    template = """
Summary
Total number of tests = $tests
Time = $time
"""

    def __init__(self):
        self.tests = 0
        self.start_time = time.time()

    # returns a single instance
    def get():
        return Stats()

    def increment_tests(self):
        self.tests = self.tests + 1

    def print(self):
        total_time = round(time.time() - self.start_time)
        time_str = str(datetime.timedelta(seconds=total_time))
        template = Template(Stats.template)
        out = template.substitute(tests = self.tests, time = time_str)
        print(out)

class ParameterType(Enum):
    unknown = 'unknown'
    byte_like_object = 'byte-like object'
    integer = 'integer'
    any_object = 'object'
    double = 'double'
    boolean = 'boolean'
    string = 'string'
    exception = 'exception'
    exception_type = 'exception type'

    def __str__(self):
        return self.value

    def default_value(ptype):
        if ptype == ParameterType.byte_like_object:
            return 'bytes()'
        if ptype == ParameterType.integer:
            return '1'
        if ptype == ParameterType.any_object:
            # TODO: anything better?
            return '()'
        if ptype == ParameterType.double:
            return '4.2'
        if ptype == ParameterType.boolean:
            return 'True'
        if ptype == ParameterType.string:
            return '\'string\''
        if ptype == ParameterType.exception:
            return 'Exception()'
        if ptype == ParameterType.exception_type:
            return 'Exception'

        # TODO: anything better?
        return '(1, 2, 3)'

class ParameterValue:

    def __init__(self, value, extra = '', import_statement = ''):
        self.value = value
        self.extra = extra
        self.imports = Imports()
        self.imports.add(import_statement)

# contains import statements for caller classes
class Imports:

    def __init__(self):
        self.froms = set()
        self.imports = set()

    # adds a single import statement
    def add(self, string):
        if not string: return
        if string.startswith('from '): self.froms.add(string)
        elif string.startswith('import '): self.imports.add(string)
        else: self.warn('unexpected import: {0}'.format(string))

    # adds all imports startements from specified Imports instance
    def merge(self, imports):
        if not isinstance(imports, Imports):
            self.warn('not Imports passed')
            return
        for string in imports.froms:   self.froms.add(string)
        for string in imports.imports: self.imports.add(string)

    # generate Python code with imports
    # 'import ...' startements go first, then 'from ...' startements go
    def code(self):
        return '{0:s}\n{1:s}'.format('\n'.join(self.imports), '\n'.join(self.froms))

    def log(self, message):
        print_with_prefix('Imports', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class FunctionCaller:

    basic_template = """
$imports
$extra
$parameter_definitions
$module_name.$function_name($function_arguments)
"""

    def __init__(self, function):
        self.function = function
        self.update_parameter_values()
        self.prepare()

    def target(self):
        return self.function

    def clone(self):
        cloned = FunctionCaller(self.function)
        cloned.parameter_values = []
        for value in self.parameter_values: cloned.parameter_values.append(value)
        return cloned

    def prepare(self):
        if self.function.has_unknown_parameters():
            raise Exception('function has unknown parameters')
        if self.function.number_of_parameters() != len(self.parameter_values):
            raise Exception('number of parameters is not equal to number of values')

        self.imports = Imports()
        self.extra = set()
        self.parameter_definitions = list()
        self.function_arguments = list()

        self.imports.add('import ' + self.function.module)

        arg_number = 1
        for parameter_type in self.function.parameter_types:
            value = self.parameter_values[arg_number-1]
            name = 'p' + str(arg_number)

            if type(value) is ParameterValue:
                self.imports.merge(value.imports)
                self.extra.add(value.extra)
                pstr = '{0:s} = {1:s}\n'.format(name, value.value)
            else:
                pstr = '{0:s} = {1}\n'.format(name, value)

            self.parameter_definitions.append(pstr)
            self.function_arguments.append(name)
            arg_number = arg_number + 1

        template = Template(FunctionCaller.basic_template)
        self.code = template.substitute(imports = self.imports.code(),
                                        extra = '\n'.join(self.extra),
                                        parameter_definitions = '\n'.join(self.parameter_definitions),
                                        module_name = self.function.module,
                                        function_name = self.function.name,
                                        function_arguments = ', '.join(self.function_arguments))

    def set_parameters(self, n):
        self.function.set_parameters(n)
        self.update_parameter_values()

    def update_parameter_values(self):
        self.parameter_values = []
        for parameter_type in self.function.parameter_types:
            self.parameter_values.append(ParameterType.default_value(parameter_type))

    def set_parameter_value(self, arg_number, value):
        self.parameter_values[arg_number - 1] = value

        # TODO: can it be called in call()
        self.prepare()

    def get_parameter_values(self):
        return self.parameter_values

    def call(self):
        self.log('run the following code:\n\n' + self.code)
        exec(self.code)

    def log(self, message):
        print_with_prefix('FunctionCaller', message)

class ConstructorCaller:

    basic_template = """
$imports
$extra
$parameter_definitions
object = $class_name($constructor_arguments)
"""

    def __init__(self, clazz):
        self.clazz = clazz
        self.constructor = clazz.get_constructor()
        self.caller = FunctionCaller(self.constructor)
        self.prepare()

    def target(self):
        return self.constructor

    def prepare(self):
        if self.constructor == None:
            self.warn('could not find a constructor of class: {0}'.format(clazz.name))
            return

        self.caller.prepare()

        self.imports = self.caller.imports
        self.extra = self.caller.extra

        self.parameter_definitions = list()
        self.parameter_definitions.extend(self.caller.parameter_definitions)

        self.constructor_arguments = list()
        self.constructor_arguments.extend(self.caller.function_arguments)

        self.imports.add('from {0:s} import {1:s}'.format(self.clazz.module, self.clazz.name))

        template = Template(ConstructorCaller.basic_template)
        self.code = template.substitute(imports = self.imports.code(),
                                        extra = '\n'.join(self.extra),
                                        parameter_definitions = '\n'.join(self.caller.parameter_definitions),
                                        class_name = self.clazz.name,
                                        constructor_arguments = ', '.join(self.caller.function_arguments))

    def set_parameters(self, n):
        self.caller.set_parameters(n)

    def set_parameter_value(self, arg_number, value):
        self.caller.set_parameter_value(arg_number, value)

    def get_parameter_values(self):
        return self.caller.get_parameter_values()

    def call(self):
        if self.constructor == None:
            self.warn('could not find a constructor of class: {0}'.format(clazz.name))
            return
        self.prepare()
        self.log('run the following code:\n' + self.code)
        exec(self.code)

    def log(self, message):
        print_with_prefix('ConstructorCaller', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

    def classname(self):
        return self.clazz.name

class MethodCaller:

    basic_template = """
$imports
$extra
$constructor_parameter_definitions
object = $class_name($constructor_arguments)
$method_parameter_definitions
r = object.$method_name($method_arguments)
"""

    def __init__(self, method, constructor_caller):
        self.method = method
        self.constructor_caller = constructor_caller
        self.caller = FunctionCaller(method)

        # it needs to be called here because TestDump requests the code before execution
        # to prevent data lose if python crashes
        self.prepare()

    def clone(self):
        cloned = MethodCaller(self.method, self.constructor_caller)
        cloned.caller = self.caller.clone()
        return cloned

    def target(self):
        return self.method

    def prepare(self, imports = Imports(), extra = set()):
        self.constructor_caller.prepare()
        self.caller.prepare()

        self.imports = imports
        self.imports.merge(self.constructor_caller.imports)
        self.imports.merge(self.caller.imports)

        self.extra = extra
        self.extra = self.extra.union(self.constructor_caller.extra)
        self.extra = self.extra.union(self.caller.extra)

        self.constructor_parameter_definitions = self.constructor_caller.parameter_definitions
        self.constructor_arguments = self.constructor_caller.constructor_arguments

        self.method_parameter_definitions = self.caller.parameter_definitions
        self.method_arguments = self.caller.function_arguments

        template = Template(MethodCaller.basic_template)
        self.code = template.substitute(imports = self.imports.code(),
                                        extra = '\n'.join(self.extra),
                                        class_name = self.constructor_caller.classname(),
                                        constructor_parameter_definitions = '\n'.join(self.constructor_parameter_definitions),
                                        constructor_arguments = ', '.join(self.constructor_arguments),
                                        method_name = self.method.name,
                                        method_parameter_definitions = '\n'.join(self.method_parameter_definitions),
                                        method_arguments = ', '.join(self.method_arguments))

    def set_parameters(self, n):
        self.caller.set_parameters(n)

    def set_parameter_value(self, arg_number, value):
        self.caller.set_parameter_value(arg_number, value)

    def get_parameter_values(self):
        return self.caller.get_parameter_values()

    def call(self):
        self.prepare()
        self.log('run the following code:\n' + self.code)
        exec(self.code)

    def log(self, message):
        print_with_prefix('MethodCaller', message)

class CoroutineChecker:

    template = """
$base_caller_code
if not 'throw' in dir(r) and not 'send' in dir(r) and not 'close' in dir(r):
    raise Exception('not a coroutine')
"""

    def __init__(self, caller):
        self.caller = caller

    def prepare(self):
        self.caller.prepare()
        template = Template(CoroutineChecker.template)
        self.code = template.substitute(base_caller_code = self.caller.code)

    def is_coroutine(self):
        self.prepare()
        self.log('run the following code (check for a coroutine):\n' + self.code)
        try:
            exec(self.code)
            return True
        except Exception:
            return False

    def log(self, message):
        print_with_prefix('CoroutineChecker', message)

class SubsequentMethodCaller:

    template = """
$base_caller_code
$parameter_definitions
r.$method_name($method_arguments)
"""

    def __init__(self, caller, method_name, parameter_types = []):
        self.caller = caller
        self.method_name = method_name
        self.parameter_types = parameter_types
        self.parameter_values = []
        for parameter_type in parameter_types:
            self.parameter_values.append(ParameterType.default_value(parameter_type))
        self.prepare()

    def prepare(self):
        self.imports = Imports()
        self.extra = set()
        self.parameter_definitions = list()
        self.method_arguments = list()

        arg_number = 1
        for parameter_type in self.parameter_types:
            value = self.parameter_values[arg_number-1]
            name = 'p' + str(arg_number)

            if type(value) is ParameterValue:
                self.imports.megre(value.imports)
                self.extra.add(value.extra)
                pstr = '{0:s} = {1:s}\n'.format(name, value.value)
            else:
                pstr = '{0:s} = {1:s}\n'.format(name, value)

            self.parameter_definitions.append(pstr)
            self.method_arguments.append(name)
            arg_number = arg_number + 1

        self.caller.prepare(self.imports, self.extra)

        template = Template(SubsequentMethodCaller.template)
        self.code = template.substitute(base_caller_code = self.caller.code,
                                        parameter_definitions = '\n'.join(self.parameter_definitions),
                                        method_name = self.method_name,
                                        method_arguments = ', '.join(self.method_arguments))

    def call(self):
        self.prepare()
        self.log('run the following code:\n' + self.code)
        exec(self.code)

    def set_parameter_value(self, arg_number, value):
        self.parameter_values[arg_number - 1] = value
        # TODO: can it be called in call()
        self.prepare()

    def log(self, message):
        print_with_prefix('SubsequentMethodCaller', message)

class TargetCallable:

    def __init__(self, filename, module, name):
        self.filename = filename
        self.module = module
        self.name = name
        self.unknown_parameters = True
        self.parameter_types = []
        self.default_values = []

    def has_no_parameters(self): return len(self.parameter_types) == 0
    def has_unknown_parameters(self): return self.unknown_parameters
    def no_unknown_parameters(self): self.unknown_parameters = False
    def has_default_value(self, index):
        if self.has_no_parameters(): return False
        else: return self.default_values[index-1] != None

    def get_default_value(self, index):
        if self.has_no_parameters(): return None
        else: return self.default_values[index-1]

    def reset_parameter_types(self):
        self.parameter_types = []
        self.default_values = []

    def set_parameters(self, n):
        self.reset_parameter_types()
        for i in range(0, n): self.add_parameter(ParameterType.any_object)
        self.no_unknown_parameters()

    def number_of_parameters(self):
        return len(self.parameter_types)

    def number_of_required_parameters(self):
        result = 0
        for value in self.default_values:
            if value == None: result = result + 1
        return result

    def add_parameter(self, parameter_type, default_value = None):
        self.parameter_types.append(parameter_type)
        self.default_values.append(default_value)

class TargetFunction(TargetCallable):

    def __init__(self, filename, module, name):
        super().__init__(filename, module, name)

    def fullname(self):
        return self.module + '.' + self.name

class TargetClass:

    def __init__(self, filename, module, name):
        self.filename = filename
        self.module = module
        self.name = name
        self.methods = {}

    def add_method(self, method):
        self.methods[method.name] = method

    def get_methods(self):
        methods = []
        for method_name in self.methods: methods.append(self.methods[method_name])
        return methods

    def fullname(self):
        return self.module + '.' + self.name

    def get_constructor(self):
        for method_name in self.methods:
            if method_name == '__init__':
                return self.methods[method_name]

        return None

    def has_constructor(self):
        return self.get_constructor() != None

class TargetMethod(TargetCallable):

    def __init__(self, name, module, clazz):
        super().__init__(None, module, name)
        self.clazz = clazz

    def fullname(self):
        return self.module + '.' + self.clazz.name + '.' + self.name

class TestDump:

    def __init__(self, path):
        self.path = path
        self.next_indexes = {}

    def store(self, caller):
        if self.path == None: return

        key = None
        if type(caller) == FunctionCaller:
            subdir = '{0:s}'.format(caller.function.module)
            key = '{0:s}_{1:s}'.format(caller.function.module, caller.function.name)
        elif type(caller) == MethodCaller:
            subdir = '{0:s}/{1:s}'.format(caller.method.module, caller.method.clazz.name)
            key = '{0:s}_{1:s}'.format(caller.method.clazz.name, caller.method.name)
        elif type(caller) == SubsequentMethodCaller:
            subdir = '{0:s}/{1:s}'.format(caller.caller.method.module, caller.caller.method.clazz.name)
            key = '{0:s}_{1:s}_{2:s}'.format(caller.caller.method.clazz.name, caller.caller.method.name, caller.method_name)
        else:
            raise Exception('Unknown caller')

        key = key.replace('.', '_')

        next_index = 0
        if key in self.next_indexes:
            next_index = self.next_indexes[key]

        directory = '{0:s}/{1:s}'.format(self.path, subdir)
        if os.path.isfile(directory):
            raise Exception('{0:s} is a file, not a directory'.format(directory))

        if not os.path.isdir(directory):
            os.makedirs(directory)

        fullpath = '{0:s}/{1:s}_{2:d}.py'.format(directory, key, next_index)
        next_index += 1
        self.next_indexes[key] = next_index

        self.log('save code to ' + fullpath)

        with open(fullpath, "w") as text_file:
            text_file.write(caller.code)

    def log(self, message):
        print_with_prefix('TestDump', message)

class FunctionCallerFactory:

    def __init__(self, function):   self.function = function
    def create(self):               return FunctionCaller(self.function)
    def target(self):               return self.function

class MethodCallerFactory:

    def __init__(self, method, constructor_caller):
        self.method = method
        self.constructor_caller = constructor_caller

    def create(self):   return MethodCaller(self.method, self.constructor_caller)
    def target(self):   return self.method
