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

NO_EXCLUDES = []
NO_COROUTINE_FUZZING = False

# TODO: move it to BaseFuzzer
fuzzing_values = ('42', '42.3', 'True', 'False', '()', '[]', '{}', '{"a":10}', 'bytes()',
                  'bytearray()', '"ololo"', 'frozenset()', 'set()',
                  'Exception', 'Exception()',
                  ParameterValue('sys.maxsize', 'import sys'), ParameterValue('-sys.maxsize-1', 'import sys'),
                  'float("inf")', 'float("-inf")',
                  '"x" * 2 ** 20', 'range(0, 2**20)',
                  '("ololo",) * 2 ** 20', '(42,) * 2 ** 20', 'bytes("x" * 2**20)', 'bytearray("x" * 2**20)',
                  '[(0), (0)]', '([0], [0])',
                  ParameterValue('A()', 'class A: pass'))

general_parameter_values = ('42', '"test"', 'True', '(1,2)', '[1,2]', '{"a":3}', 'bytes()', 'bytearray()', '42.3')

# base class for fuzzers, contains common methods
class BaseFuzzer:

    def __init__(self, path = None, excludes = []):
        self.dump = TestDump(path)
        self.excludes = excludes

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

    def __init__(self, function, path = None, excludes = []):
        super().__init__(path, excludes)
        self.function = function
        self.path = path

    def skip(self):
        if super().skip(self.function): return True

        if self.function.has_no_parameters():
            self.log('function doesn\'t have parameters, skip')
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

    def __init__(self, caller, path = None):
        super().__init__(path)
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
                for value in general_parameter_values:
                    caller.set_parameter_value(current_arg_number, value)
                    if self.could_make_successful_call(caller): return
                    if self.changed_parameters_number: return
        else:
            if self.could_set_default_value(caller, current_arg_number):
                self.search(caller, current_arg_number + 1, number_of_parameters)
            else:
                for value in general_parameter_values:
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
            if 'takes no arguments' in msg:
                n = 0
            elif 'takes exactly one argument' in msg:
                n = 1
            elif 'takes exactly ' in msg:
                start = msg.index('takes exactly ') + len('takes exactly ')
                end = msg.index(' ', start)
                string = msg[start:end].strip()
                try:
                    n = int(string)
                except: pass
            if n != None:
                caller.set_parameters(n)
                self.changed_parameters_number = True
                self.found = True
                self.log('changed parameter number to {0:d}'
                         .format(self.caller.target().number_of_parameters()))
                return False
        return False

    def log(self, message):
        core.print_with_prefix('CorrectParametersFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class HardCorrectParametersFuzzer(BaseFunctionFuzzer):

    def __init__(self, caller_factory, path = None, max_params = 3):
        super().__init__(path)
        self.caller_factory = caller_factory
        self.max_params = max_params
        self.found = False

    def success(self):      return self.found
    def get_caller(self):   return self.caller

    def run(self):
        self.log('look for correct parameters for: ' + self.caller_factory.target().name)
        for n in range(1, self.max_params+1):
            self.log('parameter number guess: {0:d}'.format(n))
            self.set_parameters(n)
            self.caller = self.caller_factory.create()
            fuzzer = CorrectParametersFuzzer(self.caller, self.path)
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

    def __init__(self, function, path = None, excludes = []):
        super().__init__(function, path, excludes)

    def fuzz(self):
        # first, try to find parameter values which lead to a successful invocation
        successful_caller = None
        if self.function.has_unknown_parameters():
            self.warn('function with unknown parameters: ' + self.function.name)
            fuzzer = HardCorrectParametersFuzzer(FunctionCallerFactory(self.function), self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        elif self.function.number_of_parameters() == 1:
            successful_caller = FunctionCaller(self.function)
        else:
            fuzzer = CorrectParametersFuzzer(FunctionCaller(self.function), self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        if successful_caller == None:
            self.warn('could not find correct parameter values, skip: ' + self.function.fullname())
            return
        self.log('run fuzzing for function {0:s} with {1:d} parameters'
                 .format(self.function.name, self.function.number_of_parameters()))
        for parameter_index in range(1, self.function.number_of_parameters()+1):
            caller = successful_caller.clone()
            for value in fuzzing_values:
                caller.set_parameter_value(parameter_index, value)
                self.run_and_dump_code(caller)

    def log(self, message):
        core.print_with_prefix('SmartFunctionFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class SmartClassFuzzer(BaseFuzzer):

    def __init__(self, clazz, path = None, excludes = None):
        super().__init__(path, excludes)
        self.clazz = clazz
        self.path = path

    def run(self):
        self.log('try to fuzz class: ' + self.clazz.name)
        self.log('sources: ' + self.clazz.filename)

        # make sure that we can call a constructor,
        # and get an instance of the class
        # if we can't, we can't continue fuzzing
        if not self.clazz.has_constructor():
            self.warn('could not find a constructor of class: {0}'.format(self.clazz.name))
            return
        finder = CorrectParametersFuzzer(ConstructorCaller(self.clazz))
        finder.run()
        if not finder.success():
            self.warn('could not create an instance of "{0:s}" class, skip fuzzing'. format(self.clazz.name))
            return
        constructor_caller = finder.get_caller()

        # start actual fuzzing
        for method in self.clazz.get_methods():
            SmartMethodFuzzer(method, constructor_caller, self.path, self.excludes).run()

    def log(self, message):
        core.print_with_prefix('SmartClassFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class SmartMethodFuzzer(BaseFuzzer):

    def __init__(self, method, constructor_caller, path = None, excludes = None, fuzz_coroutine = True):
        super().__init__(path, excludes)
        self.method = method
        self.constructor_caller = constructor_caller
        self.path = path
        self.fuzz_coroutine = fuzz_coroutine

    def run(self):
        if self.skip(self.method):
            self.log('skip fuzzing of ' + self.method.fullname())
            return
        # first, try to find parameter values which lead to a successful invocation
        successful_caller = None
        if self.method.has_unknown_parameters():
            self.warn('method with unknown parameters: ' + self.method.fullname())
            fuzzer = HardCorrectParametersFuzzer(MethodCallerFactory(self.method, self.constructor_caller), self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        elif self.method.number_of_parameters() == 1:
            successful_caller = MethodCaller(self.method, self.constructor_caller)
        else:
            fuzzer = CorrectParametersFuzzer(MethodCaller(self.method, self.constructor_caller), self.path)
            fuzzer.run()
            if fuzzer.success(): successful_caller = fuzzer.get_caller()
        if successful_caller == None:
            self.warn('could not find correct parameter values, skip: ' + self.method.fullname())
            return
        self.log('run fuzzing for method {0:s} with {1:d} parameters'
                 .format(self.method.fullname(), self.method.number_of_parameters()))
        if self.method.has_no_parameters() and self.fuzz_coroutine:
            CoroutineFuzzer(successful_caller.clone(), self.path).run()
        for parameter_index in range(1, self.method.number_of_parameters()+1):
            caller = successful_caller.clone()
            for value in fuzzing_values:
                caller.set_parameter_value(parameter_index, value)
                self.run_and_dump_code(caller)
                if self.fuzz_coroutine: CoroutineFuzzer(caller, self.path).run()

    def log(self, message):
        core.print_with_prefix('SmartMethodFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

class CoroutineFuzzer(BaseFuzzer):

    def __init__(self, caller, path = None):
        super().__init__(path)
        self.caller = caller
        self.path = path

    def run(self):
        checker = CoroutineChecker(self.caller)
        if not checker.is_coroutine():
            self.log('it is not a coroutine')
            return
        self.log('coroutine found')
        close_caller = SubsequentMethodCaller(self.caller, 'close')
        self.run_and_dump_code(close_caller)
        fuzzer = SubsequentMethodFuzzer(self.caller, self.path, 'send', [ParameterType.any_object],
                                        NO_EXCLUDES, NO_COROUTINE_FUZZING)
        fuzzer.run()
        # TODO: what does it expect in the third parameter? TracebackException?
        fuzzer = SubsequentMethodFuzzer(self.caller, self.path, 'throw',
                                        [ParameterType.exception_type, ParameterType.exception, ParameterType.any_object],
                                        NO_EXCLUDES, NO_COROUTINE_FUZZING)
        fuzzer.run()

    def log(self, message):
        core.print_with_prefix('CoroutineFuzzer', message)

class SubsequentMethodFuzzer(SmartMethodFuzzer):

    def __init__(self, base_caller, path, subsequent_method_name, parameter_types = [], excludes = [], fuzz_coroutine = True):
        super().__init__(base_caller.method, base_caller.constructor_caller, path, excludes, fuzz_coroutine)
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
            if self.fuzz_coroutine: CoroutineFuzzer(caller, self.path).run()
        else:
            self.fuzz_hard(caller, 1)

    def fuzz_hard(self, caller, current_arg_number):
        if current_arg_number == self.get_number_of_parameters():
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.run_and_dump_code(caller)
                if self.fuzz_coroutine: CoroutineFuzzer(caller, self.path).run()
        else:
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.fuzz_hard(caller, current_arg_number + 1)

    def get_number_of_parameters(self): return len(self.parameter_types)

    def log(self, message):
        core.print_with_prefix('SubsequentMethodFuzzer', message)
