#!/usr/bin/python

import textwrap
import os
import core

from core import ParameterType
from core import ParameterValue
from core import FunctionCaller
from core import MethodCaller
from core import ConstructorCaller
from core import TestDump
from core import CoroutineChecker
from core import SubsequentMethodCaller
from core import Stats
from core import FunctionCallerFactory, MethodCallerFactory

NO_PATH = None
NO_EXCLUDES = []
NO_VALUES = []
DISABLE_COROUTINE_FUZZING = False
ENABLE_COROUTINE_FUZZING = True

GET_TRACEBACK_CODE = """
try:
    raise Exception('ololo')
except: tb = sys.exc_info()[2]
"""

DEFAULT_FUZZING_VALUES = ('42', '42.3', '2 ** 16', '-1 * 2 ** 16', 'True', 'False', '()', '[]', '{}', '{"a":10}', 'bytes()', 'None',
                          'bytearray()', '"ololo"', 'frozenset()', 'set()',
                          'Exception', 'Exception()',
                          'float("inf")', 'float("-inf")',
                          '"x" * 2 ** 20', 'range(0, 2**20)',
                          '("ololo",) * 2 ** 20', '(42,) * 2 ** 20', 'bytes("x" * 2**20)', 'bytearray("x" * 2**20)',
                          '[(0), (0)]', '([0], [0])',
                          ParameterValue('A()', 'class A: pass'),
                          ParameterValue('tb', GET_TRACEBACK_CODE, 'import sys'))

# the following value often cause "hangs"
# ParameterValue('sys.maxsize', '', 'import sys'), ParameterValue('-sys.maxsize-1', '', 'import sys'),

DEFAULT_GENERAL_PARAMETER_VALUES = ('42', '"test"', 'True', '(1,2)', '[1,2]', '{"a":3}', 'bytes()', 'bytearray()', '42.3', 'None',
                                    ParameterValue('sys.exc_info()[2]', '', 'import sys'),
                                    ParameterValue('tb', GET_TRACEBACK_CODE, 'import sys'))

DEFAULT_MAX_PARAM_NUMBER = 3

# base class for fuzzers, contains common methods
class BaseFuzzer:

    def __init__(self):
        self.excludes = NO_EXCLUDES
        self.path = NO_PATH
        self.fuzzing_values = NO_VALUES
        self.general_parameter_values = NO_VALUES

    # sets a path where the fuzzer should dump generated code to
    def set_output_path(self, path):
        self.path = path
        self.dump = TestDump(path)

    # sets an exclude list
    def set_excludes(self, excludes):
        self.excludes = excludes

    def set_fuzzing_values(self, values):
        self.fuzzing_values = []
        self.add_fuzzing_values(values)

    def add_fuzzing_values(self, values):
        self.fuzzing_values.extend(values)

    def set_general_parameter_values(self, values):
        self.general_parameter_values = []
        self.add_general_parameter_values(values)

    def add_general_parameter_values(self, values):
        self.general_parameter_values.extend(values)

    # runs and stores generated code to specified location
    # all exceptions are caught and logged in this method
    def run_and_dump_code(self, caller):
        result = False
        self.dump.store(caller)
        try:
            caller.call()
            self.log('wow, it succeded')
            result = True
        except Exception as err:
            self.exception = err
            self.log('exception {0}: {1}'.format(type(err), str(err)))
        Stats.get().increment_tests()
        return result

    # checks if a target should be skipped
    # returns true if a target should not be fuzzed, false otherwise
    def skip(self, target):
        if self.excludes:
            if isinstance(self.excludes, list):
                for exclude in self.excludes:
                    if exclude in target.fullname(): return True
            else:
                if self.excludes in target.fullname(): return True

        return False

    def get_exception(self): return self.exception

class BaseFunctionFuzzer(BaseFuzzer):

    def __init__(self, function):
        super().__init__()
        self.function = function

    def skip(self):
        if super().skip(self.function): return True

        if not self.function.has_unknown_parameters() and self.function.has_no_parameters():
            self.log('function "{0:s}" doesn\'t have parameters, skip'.format(self.function.fullname()))
            return True

        # TODO: those ifs are ugly
        #       need to define a class wich check if we should skip module/function/method/etc,
        #       and check instances of this class in a loop
        if self.function.module == 'os':
            self.log('skip \'os\' module')
            return True

        if self.function.module == 'signal' or self.function.module == '_signal':
            self.log('skip \'signal\' module')
            return True

        if self.function.module == 'faulthandler':
            self.log('skip \'faulthandler\' module')
            return True

        return False

    def run(self):
        if self.skip(): return
        self.log('try to fuzz function: ' + self.function.name)
        self.log('sources: ' + self.function.filename)

        # run actual fuzzing
        self.fuzz()

# looks for a set of parameters which results to successful call
# it just exits if a callable has 0 or 1 parameter
class CorrectParametersFuzzer(BaseFuzzer):

    def __init__(self, caller):
        super().__init__()
        self.caller = caller
        self.found = False
        self.changed_parameters_number = False

    def success(self):      return self.found
    def get_caller(self):   return self.caller

    def run(self):
        while True:
            if self.caller.target().has_no_parameters():
                self.log('no parameters, try to call it')
                if self.could_make_successful_call(self.caller):
                    self.found = True
                    break
                if not self.changed_parameters_number:
                    self.warn('no parameters, no successful call')
                    break
            self.log('look for correct parameters for {0:s} with {1:d} parameters'
                     .format(self.caller.target().name, self.caller.target().number_of_parameters()))
            self.changed_parameters_number = False
            self.found = False
            self.search(self.caller, 1, self.caller.target().number_of_parameters())
            if self.changed_parameters_number:
                self.changed_parameters_number = False
                continue
            break

    # recursive search
    def search(self, caller, current_arg_number, number_of_parameters):
        if self.found: return
        if current_arg_number == number_of_parameters:
            if self.could_set_default_value(caller, current_arg_number):
                if self.could_make_successful_call(caller): return
                if self.changed_parameters_number: return
            else:
                for value in self.general_parameter_values:
                    caller.set_parameter_value(current_arg_number, value)
                    if self.could_make_successful_call(caller): return
                    if self.changed_parameters_number: return
        else:
            if self.could_set_default_value(caller, current_arg_number):
                self.search(caller, current_arg_number + 1, number_of_parameters)
            else:
                for value in self.general_parameter_values:
                    caller.set_parameter_value(current_arg_number, value)
                    self.search(caller, current_arg_number + 1, number_of_parameters)
                    if self.found: return

    # if a parameter has a default value, it's set to a caller, and true is returned
    # false otherwise
    def could_set_default_value(self, caller, current_arg_number):
        if self.caller.target().has_default_value(current_arg_number):
            value = self.caller.target().get_default_value(current_arg_number)
            caller.set_parameter_value(current_arg_number, value)
            return True
        else: return False

    # run a caller, and checks if the call was successful (no exception thrown)
    # if an exception was thrown, it tries to analyze it to figure out
    # if the callable has wrong parameters number
    def could_make_successful_call(self, caller):
        self.found = self.run_and_dump_code(caller)
        if self.found:
            self.log('found correct parameter values: {0}'.format(caller.get_parameter_values()))
            return True
        if self.get_exception() != None:
            msg = str(self.get_exception())
            n = None
            if 'takes no arguments' in msg or 'takes no parameters' in msg:
                n = 0
            elif 'takes exactly one argument' in msg:
                n = 1
            elif 'takes exactly ' in msg:
                n = self.get_n_from_message(msg, 'takes exactly ')
            elif 'takes at most ' in msg:
                n = self.get_n_from_message(msg, 'takes at most ')
            elif 'expected at most ' in msg:
                n = self.get_n_from_message(msg, 'expected at most ')
            if n != None:
                caller.set_parameters(n)
                self.changed_parameters_number = True
                self.found = True
                self.log('changed parameter number to {0:d}'
                         .format(self.caller.target().number_of_parameters()))
                return False
        return False

    def get_n_from_message(self, msg, string):
        start = msg.index(string) + len(string)
        end = msg.index(' ', start)
        string = msg[start:end].strip()
        try:
            return int(string)
        except: return None

    def log(self, message):
        core.print_with_prefix('CorrectParametersFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class HardCorrectParametersFuzzer(BaseFuzzer):

    def __init__(self, caller_factory):
        super().__init__()
        self.caller_factory = caller_factory
        self.max_params = DEFAULT_MAX_PARAM_NUMBER
        self.found = False

    def set_max_params(self, max_params): self.max_params = max_params
    def success(self):      return self.found
    def get_caller(self):   return self.caller

    def run(self):
        self.log('look for correct parameters for: ' + self.caller_factory.target().name)
        for n in range(1, self.max_params+1):
            self.log('parameter number guess: {0:d}'.format(n))
            self.set_parameters(n)
            self.caller = self.caller_factory.create()
            fuzzer = CorrectParametersFuzzer(self.caller)
            fuzzer.set_general_parameter_values(self.general_parameter_values)
            fuzzer.set_output_path(self.path)
            fuzzer.run()
            if fuzzer.success():
                self.found = True
                return

    def set_parameters(self, n):
        self.caller_factory.target().reset_parameter_types();
        for i in range(0, n): self.caller_factory.target().add_parameter(ParameterType.any_object)
        self.caller_factory.target().no_unknown_parameters()

    def log(self, message):
        core.print_with_prefix('HardCorrectParametersFuzzer', message)

# TODO: support different bindings of parameters
#       https://docs.python.org/3/library/inspect.html#inspect.Parameter.kind
# TODO: fuzz different number of parameters - range(self.function.number_of_required_parameters(), self.number_of_parameters())
class SmartFunctionFuzzer(BaseFunctionFuzzer):

    def __init__(self, function):
        super().__init__(function)

    def fuzz(self):
        # first, try to find parameter values which lead to a successful invocation
        successful_caller = None
        if self.function.has_unknown_parameters():
            self.warn('function with unknown parameters: ' + self.function.name)
            fuzzer = HardCorrectParametersFuzzer(FunctionCallerFactory(self.function))
            fuzzer.set_general_parameter_values(self.general_parameter_values)
            fuzzer.set_output_path(self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        elif self.function.number_of_parameters() == 1:
            successful_caller = FunctionCaller(self.function)
        else:
            fuzzer = CorrectParametersFuzzer(FunctionCaller(self.function))
            fuzzer.set_general_parameter_values(self.general_parameter_values)
            fuzzer.set_output_path(self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        if successful_caller == None:
            self.warn('could not find correct parameter values, skip: ' + self.function.fullname())
            return
        self.log('run fuzzing for function {0:s} with {1:d} parameters'
                 .format(self.function.name, self.function.number_of_parameters()))
        for parameter_index in range(1, self.function.number_of_parameters()+1):
            caller = successful_caller.clone()
            for value in self.fuzzing_values:
                caller.set_parameter_value(parameter_index, value)
                self.run_and_dump_code(caller)

    def log(self, message):
        core.print_with_prefix('SmartFunctionFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class SmartClassFuzzer(BaseFuzzer):

    def __init__(self, clazz):
        super().__init__()
        self.clazz = clazz

    def run(self):
        self.log('try to fuzz class: ' + self.clazz.name)
        self.log('sources: ' + self.clazz.filename)

        # make sure that we can call a constructor,
        # and get an instance of the class
        # if we can't, we can't continue fuzzing
        if not self.clazz.has_constructor():
            self.warn('could not find a constructor of class: {0}'.format(self.clazz.name))
            return
        fuzzer = CorrectParametersFuzzer(ConstructorCaller(self.clazz))
        fuzzer.set_general_parameter_values(self.general_parameter_values)
        fuzzer.set_output_path(self.path)
        fuzzer.run()
        if not fuzzer.success():
            self.warn('could not create an instance of "{0:s}" class, skip fuzzing'. format(self.clazz.name))
            return
        constructor_caller = fuzzer.get_caller()

        # start actual fuzzing
        for method in self.clazz.get_methods():
            fuzzer = SmartMethodFuzzer(method, constructor_caller)
            fuzzer.enable_coroutine_fuzzing()
            fuzzer.set_fuzzing_values(self.fuzzing_values)
            fuzzer.set_general_parameter_values(self.general_parameter_values)
            fuzzer.set_output_path(self.path)
            fuzzer.set_excludes(self.excludes)
            fuzzer.run()

    def log(self, message):
        core.print_with_prefix('SmartClassFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class SmartMethodFuzzer(BaseFuzzer):

    def __init__(self, method, constructor_caller):
        super().__init__()
        self.method = method
        self.constructor_caller = constructor_caller
        self.fuzz_coroutine = ENABLE_COROUTINE_FUZZING

    def disable_coroutine_fuzzing(self): self.fuzz_coroutine = False
    def enable_coroutine_fuzzing(self):  self.fuzz_coroutine = True

    def run(self):
        if self.skip(self.method):
            self.log('skip fuzzing of ' + self.method.fullname())
            return
        # first, try to find parameter values which lead to a successful invocation
        successful_caller = None
        if self.method.has_unknown_parameters():
            self.warn('method with unknown parameters: ' + self.method.fullname())
            fuzzer = HardCorrectParametersFuzzer(MethodCallerFactory(self.method, self.constructor_caller))
            fuzzer.set_general_parameter_values(self.general_parameter_values)
            fuzzer.set_output_path(self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        elif self.method.number_of_parameters() == 1:
            successful_caller = MethodCaller(self.method, self.constructor_caller)
        else:
            fuzzer = CorrectParametersFuzzer(MethodCaller(self.method, self.constructor_caller))
            fuzzer.set_general_parameter_values(self.general_parameter_values)
            fuzzer.set_output_path(self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        if successful_caller == None:
            self.warn('could not find correct parameter values, skip: ' + self.method.fullname())
            return
        self.log('run fuzzing for method {0:s} with {1:d} parameters'
                 .format(self.method.fullname(), self.method.number_of_parameters()))
        if self.method.has_no_parameters() and self.fuzz_coroutine:
            fuzzer = CoroutineFuzzer(successful_caller.clone())
            fuzzer.set_fuzzing_values(self.fuzzing_values)
            fuzzer.set_general_parameter_values(self.general_parameter_values)
            fuzzer.set_output_path(self.path)
            fuzzer.run()
        for parameter_index in range(1, self.method.number_of_parameters()+1):
            caller = successful_caller.clone()
            for value in self.fuzzing_values:
                caller.set_parameter_value(parameter_index, value)
                self.run_and_dump_code(caller)
                if self.fuzz_coroutine:
                    fuzzer = CoroutineFuzzer(caller)
                    fuzzer.set_fuzzing_values(self.fuzzing_values)
                    fuzzer.set_general_parameter_values(self.general_parameter_values)
                    fuzzer.set_output_path(self.path)
                    fuzzer.run()

    def log(self, message):
        core.print_with_prefix('SmartMethodFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class CoroutineFuzzer(BaseFuzzer):

    def __init__(self, caller):
        super().__init__()
        self.caller = caller

    def run(self):
        if not CoroutineChecker(self.caller).is_coroutine():
            self.log('it is not a coroutine, quit')
            return
        self.log('coroutine found')
        close_caller = SubsequentMethodCaller(self.caller, 'close')
        self.run_and_dump_code(close_caller)
        fuzzer = SubsequentMethodFuzzer(self.caller, self.path, 'send', [ParameterType.any_object])
        fuzzer.set_fuzzing_values(self.fuzzing_values)
        fuzzer.set_general_parameter_values(self.general_parameter_values)
        fuzzer.disable_coroutine_fuzzing()
        fuzzer.run()
        # TODO: what does it expect in the third parameter? TracebackException?
        fuzzer = SubsequentMethodFuzzer(self.caller, self.path, 'throw',
                                        [ParameterType.exception_type, ParameterType.exception, ParameterType.any_object])
        fuzzer.set_fuzzing_values(self.fuzzing_values)
        fuzzer.set_general_parameter_values(self.general_parameter_values)
        fuzzer.disable_coroutine_fuzzing()
        fuzzer.run()

    def log(self, message):
        core.print_with_prefix('CoroutineFuzzer', message)

class SubsequentMethodFuzzer(SmartMethodFuzzer):

    def __init__(self, base_caller, subsequent_method_name, parameter_types = []):
        super().__init__(base_caller.method, base_caller.constructor_caller)
        self.base_caller = base_caller
        self.subsequent_method_name = subsequent_method_name
        self.parameter_types = parameter_types

    def run(self):
        self.log('run fuzzing for method {0:s} with {1:d} parameters'
                 .format(self.base_caller.target().fullname() + '.' + self.subsequent_method_name, self.get_number_of_parameters()))
        caller = SubsequentMethodCaller(self.base_caller, self.subsequent_method_name, self.parameter_types)
        if self.get_number_of_parameters() == 0:
            self.log('method does not have parameters, just call it')
            self.run_and_dump_code(caller)
            if self.fuzz_coroutine:
                fuzzer = CoroutineFuzzer(caller)
                fuzzer.set_output_path(self.path)
                fuzzer.run()
        else:
            self.fuzz_hard(caller, 1)

    def fuzz_hard(self, caller, current_arg_number):
        if current_arg_number == self.get_number_of_parameters():
            for value in self.fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.run_and_dump_code(caller)
                if self.fuzz_coroutine:
                    fuzzer = CoroutineFuzzer(caller)
                    fuzzer.set_output_path(self.path)
                    fuzzer.run()
        else:
            for value in self.fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.fuzz_hard(caller, current_arg_number + 1)

    def get_number_of_parameters(self): return len(self.parameter_types)

    def log(self, message):
        core.print_with_prefix('SubsequentMethodFuzzer', message)
