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
    long = 'long'
    unsigned_long = 'unsigned long'
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
    path_t = 'path-like object'
    dir_fd = 'dir_fd'
    file_descriptor = 'file descriptor'
    uid_t = 'uid'
    gid_t = 'gid'
    FSConverter = 'FSConverter'
    pid_t = 'process id'
    sched_param = 'sched_param'
    idtype_t = 'idtype_t'
    intptr_t = 'intptr_t'
    off_t = 'offset'
    dev_t = 'device'
    path_confname = 'path_confname'
    confstr_confname = 'confstr_confname'
    sysconf_confname = 'sysconf_confname'
    io_ssize_t = 'io_ssize_t'
    exception = 'exception'
    exception_type = 'exception type'

    def __str__(self):
        return self.value

    # TODO: get rid of these terrible ifs (and also see below)
    def extract_parameter_type(pstr, default_value):
        if pstr == 'Py_buffer' or 'Py_buffer(accept' in pstr:
            return ParameterType.byte_like_object
        if pstr == 'long':
            return ParameterType.long
        if pstr.startswith('unsigned_long(bitwise'):
            return ParameterType.unsigned_long
        if pstr == 'double':
            return ParameterType.double
        if pstr == 'Py_complex_protected' or pstr == 'Py_complex':
            return ParameterType.complex_number
        if ParameterType.is_any_object(pstr):
            return ParameterType.any_object
        if ParameterType.is_ssize_t(pstr):
            return ParameterType.ssize_t
        if pstr == 'bool':
            return ParameterType.boolean
        if ParameterType.is_boolean(pstr, default_value):
            return ParameterType.boolean
        if ParameterType.is_int(pstr):
            return ParameterType.integer
        if ParameterType.is_string(pstr):
            return ParameterType.string
        if pstr == 'ascii_buffer':
            return ParameterType.ascii_buffer
        if ParameterType.is_unicode(pstr):
            return ParameterType.unicode_buffer
        if 'unsigned_int' in pstr:
            return ParameterType.unsigned_int
        if 'lzma_filter' in pstr:
            return ParameterType.lzma_filter
        if 'lzma_vli' in pstr:
            return ParameterType.lzma_vli
        if ParameterType.is_path_t(pstr):
            return ParameterType.path_t
        if ParameterType.is_dir_fd(pstr):
            return ParameterType.dir_fd
        if pstr == 'fildes':
            return ParameterType.file_descriptor
        if pstr == 'uid_t':
            return ParameterType.uid_t
        if pstr == 'gid_t':
            return ParameterType.gid_t
        if pstr == 'FSConverter':
            return ParameterType.FSConverter
        if pstr == 'pid_t' or pstr == 'id_t':
            return ParameterType.pid_t
        if pstr == 'sched_param':
            return ParameterType.sched_param
        if pstr == 'idtype_t':
            return ParameterType.idtype_t
        if pstr == 'intptr_t':
            return ParameterType.intptr_t
        if pstr == 'Py_off_t':
            return ParameterType.off_t
        if pstr == 'dev_t':
            return ParameterType.dev_t
        if pstr == 'path_confname':
            return ParameterType.path_confname
        if pstr == 'confstr_confname':
            return ParameterType.confstr_confname
        if pstr == 'sysconf_confname':
            return ParameterType.sysconf_confname
        if pstr == 'io_ssize_t':
            return ParameterType.io_ssize_t
        # we don't have ParameterType.exception here (should we?)

        return ParameterType.unknown

    def is_unicode(pstr):
        return (pstr == 'unicode'
                or pstr == 'Py_UNICODE'
                or pstr.startswith('Py_UNICODE(zeroes'))

    def is_dir_fd(pstr):
        return (pstr == 'dir_fd' or pstr.startswith('dir_fd('))

    def is_path_t(pstr):
        return (pstr == 'path_t'
                or pstr.startswith('path_t(allow_fd')
                or pstr.startswith('path_t(nullable'))

    def is_string(pstr):
        return (pstr == 'str'
                or pstr.startswith('str(accept')
                or pstr.startswith('str(c_default'))

    def is_int(pstr):
        return (pstr == 'int'
                or pstr.startswith('int(c_default')
                or pstr.startswith('int(accept')
                or pstr.startswith('int(py_default')
                or pstr.startswith('int(type'))

    def is_boolean(pstr, default_value):
        return ((pstr == 'int(c_default="0")' or pstr == 'int(c_default="1")')
                and (default_value == 'True' or default_value == 'False'))

    def is_ssize_t(pstr):
        return (pstr == 'Py_ssize_t'
                or pstr == 'ssize_t'
                or pstr.startswith('ssize_t(c_default')
                or pstr.startswith('Py_ssize_t(c_default'))

    def is_any_object(pstr):
        return (pstr == 'object'
                or pstr.startswith('object(c_default')
                or pstr.startswith('object(converter')
                or pstr.startswith('object(subclass_of')
                or pstr.startswith('object(type')
                or pstr == '\'O\'')

    def default_value(ptype):
        if ptype == ParameterType.byte_like_object:
            return 'bytes()'
        if ptype == ParameterType.integer:
            return '1'
        if ptype == ParameterType.unsigned_int:
            return '1'
        if ptype == ParameterType.long:
            return '1'
        if ptype == ParameterType.unsigned_long:
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
        if ptype == ParameterType.string:
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
        if ptype == ParameterType.path_t:
            # TODO: should it create a temp file instead of using /tmp here?
            return '/tmp'
        if ptype == ParameterType.dir_fd:
            # TODO: anything better?
            return 'rootfd'
        if ptype == ParameterType.file_descriptor:
            # TODO: anything better?
            return 'None'
        if ptype == ParameterType.uid_t:
            return '1001'
        if ptype == ParameterType.gid_t:
            return '1002'
        if ptype == ParameterType.FSConverter:
            # TODO: anything better?
            return '\'ls\''
        if ptype == ParameterType.pid_t:
            return '1234'
        if ptype == ParameterType.sched_param:
            # TODO: return os.sched_param instance
            return 'None'
        if ptype == ParameterType.idtype_t:
            return 'P_ALL'
        if ptype == ParameterType.intptr_t:
            return '2345'
        if ptype == ParameterType.off_t:
            return '42'
        if ptype == ParameterType.dev_t:
            # TODO: use os.makedev
            return 'None'
        if ptype == ParameterType.path_confname:
            # TODO: anything better?
            return 'test'
        if ptype == ParameterType.confstr_confname:
            # TODO: anyting better?
            return 'test'
        if ptype == ParameterType.sysconf_confname:
            # TODO: anything better?
            return 'test'
        if ptype == ParameterType.io_ssize_t:
            # TODO: anyting better?
            return '-1'
        if ptype == ParameterType.exception:
            return 'Exception()'
        if ptype == ParameterType.exception_type:
            return 'Exception'

        # TODO: anything better?
        return '(1, 2, 3)'

class ParameterValue:

    def __init__(self, value, extra = '', imports = ''):
        self.value = value
        self.extra = extra
        self.imports = imports

class FunctionCaller:

    basic_template = """
$imports
$extra
$parameter_definitions
$module_name.$function_name($function_arguments)
"""

    def __init__(self, function):
        self.function = function
        self.parameter_values = []
        for parameter_type in function.parameter_types:
            self.parameter_values.append(ParameterType.default_value(parameter_type))
        self.prepare()

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

        self.imports = set()
        self.extra = set()
        self.parameter_definitions = list()
        self.function_arguments = list()

        self.imports.add('import ' + self.function.module)

        arg_number = 1
        for parameter_type in self.function.parameter_types:
            value = self.parameter_values[arg_number-1]
            name = 'p' + str(arg_number)

            if type(value) is ParameterValue:
                self.imports.add(value.imports)
                self.extra.add(value.extra)
                pstr = '{0:s} = {1:s}\n'.format(name, value.value)
            else:
                pstr = '{0:s} = {1:s}\n'.format(name, value)

            self.parameter_definitions.append(pstr)
            self.function_arguments.append(name)
            arg_number = arg_number + 1

        template = Template(FunctionCaller.basic_template)
        self.code = template.substitute(imports = ''.join(self.imports),
                                        extra = ''.join(self.extra),
                                        parameter_definitions = ''.join(self.parameter_definitions),
                                        module_name = self.function.module,
                                        function_name = self.function.name,
                                        function_arguments = ', '.join(self.function_arguments))

    def set_parameter_value(self, arg_number, value):
        self.parameter_values[arg_number - 1] = value

        # TODO: can it be called in call()
        self.prepare()

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
        if self.constructor == None:
            raise Exception('couldn\'t find a constructor of class ' + clazz.name)

        self.caller = FunctionCaller(self.constructor)
        self.prepare()

    def prepare(self):
        self.caller.prepare()

        self.imports = self.caller.imports
        self.extra = self.caller.extra

        self.parameter_definitions = list()
        self.parameter_definitions.extend(self.caller.parameter_definitions)

        self.constructor_arguments = list()
        self.constructor_arguments.extend(self.caller.function_arguments)

        template = Template(ConstructorCaller.basic_template)
        self.code = template.substitute(imports = ''.join(self.imports),
                                        extra = ''.join(self.extra),
                                        parameter_definitions = ''.join(self.caller.parameter_definitions),
                                        class_name = self.clazz.name,
                                        constructor_arguments = ', '.join(self.caller.function_arguments))

    def set_parameter_value(self, arg_number, value):
        self.caller.set_parameter_value(arg_number, value)

    def call(self):
        self.prepare()
        self.log('run the following code:\n' + self.code)
        exec(self.code)

    def log(self, message):
        print_with_prefix('ConstructorCaller', message)

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

    def prepare(self, imports = set(), extra = set()):
        self.constructor_caller.prepare()
        self.caller.prepare()

        self.imports = imports
        self.imports = self.imports.union(self.constructor_caller.imports)
        self.imports = self.imports.union(self.caller.imports)

        self.extra = extra
        self.extra = self.extra.union(self.constructor_caller.extra)
        self.extra = self.extra.union(self.caller.extra)

        self.constructor_parameter_definitions = self.constructor_caller.parameter_definitions
        self.constructor_arguments = self.constructor_caller.constructor_arguments

        self.method_parameter_definitions = self.caller.parameter_definitions
        self.method_arguments = self.caller.function_arguments

        template = Template(MethodCaller.basic_template)
        self.code = template.substitute(imports = ''.join(self.imports),
                                        extra = ''.join(self.extra),
                                        class_name = self.constructor_caller.classname(),
                                        constructor_parameter_definitions = ''.join(self.constructor_parameter_definitions),
                                        constructor_arguments = ', '.join(self.constructor_arguments),
                                        method_name = self.method.name,
                                        method_parameter_definitions = ''.join(self.method_parameter_definitions),
                                        method_arguments = ', '.join(self.method_arguments))

    def set_parameter_value(self, arg_number, value):
        self.caller.set_parameter_value(arg_number, value)

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
        self.imports = set()
        self.extra = set()
        self.parameter_definitions = list()
        self.method_arguments = list()

        arg_number = 1
        for parameter_type in self.parameter_types:
            value = self.parameter_values[arg_number-1]
            name = 'p' + str(arg_number)

            if type(value) is ParameterValue:
                self.imports.add(value.imports)
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
                                        parameter_definitions = ''.join(self.parameter_definitions),
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

    def has_no_parameters(self): return not self.unknown_parameters and len(self.parameter_types) == 0
    def has_unknown_parameters(self): return self.unknown_parameters
    def no_unknown_parameters(self): self.unknown_parameters = False
    def has_default_value(self, index): return self.default_values[index-1] != None
    def get_default_value(self, index): return self.default_values[index-1]
    def reset_parameter_types(self):
        self.parameter_types = []
        self.default_values = []

    def number_of_parameters(self):
        return len(self.parameter_types)

    def number_of_required_parameters(self):
        result = 0
        for value in self.default_values:
            if value == None: result = result + 1
        return result

    def add_parameter(self, parameter_type, default_value = None):
        self.parameter_types.append(parameter_type)
        self.default_values.append(None)

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

    def add_method_with_params(self, name, *parameter_types):
        method = TargetMethod(name, self.module, self)
        method.no_unknown_parameters()
        for parameter_type in parameter_types:
            method.add_parameter(parameter_type)
        self.methods[name] = method

    def add_method(self, name):
        if name in self.methods:
            raise Exception('Method already exists: ' + name)

        method = TargetMethod(name, self.module, self)
        self.methods[name] = method

        return method

    def fullname(self):
        return self.name

    def get_constructor(self):
        for method_name in self.methods:
            if self.methods[method_name].name == '__init__':
                return self.methods[method_name]

        return TargetMethod('__init__', self.module, self)

    def has_constructor(self):
        return self.get_constructor() != None

class TargetMethod(TargetCallable):

    def __init__(self, name, module, clazz):
        super().__init__(None, module, name)
        self.clazz = clazz

    def fullname(self):
        return self.module + '.' + self.name

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
