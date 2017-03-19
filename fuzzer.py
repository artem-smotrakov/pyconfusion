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

# TODO: move it to BaseFuzzer
fuzzing_values = ('42', '42.3', 'True', 'False', '()', '[]', '{}', '{"a":10}', 'bytes()',
                  'bytearray()', '"ololo"', 'frozenset()', 'set()',
                  'Exception', 'Exception()',
                  ParameterValue('sys.maxin', 'import sys'), ParameterValue('-sys.maxin-1', 'import sys'),
                  'float("inf")', 'float("-inf")',
                  '"x" * 2 ** 20', 'range(0, 2**20)',
                  '("ololo",) * 2 ** 20', '(42,) * 2 ** 20', 'bytes("x" * 2**20)', 'bytearray("x" * 2**20)',
                  '[(0), (0)]', '([0], [0])',
                  ParameterValue('A()', 'class A: pass'))

general_parameter_values = ('42', '"test"', 'True', '(1,2)', '[1,2]', '{"a":3}', 'bytes()', 'bytearray()', '42.3')

# base class for fuzzers, contains common methods
class BaseFuzzer:

    def __init__(self, path = None):
        self.dump = TestDump(path)

    def run_and_dump_code(self, caller):
        result = False
        self.dump.store(caller)
        try:
            caller.call()
            self.log('wow, it succeded')
            result = True
        except Exception as err:
            self.log('exception {0}: {1}'.format(type(err), err))
        Stats.get().increment_tests()
        return result

    # returns a subsequent method caller
    # this method should be implemented in a child class which uses try_coroutine_fuzzing()
    def create_subsequent_method_fuzzer(self, caller, path, method_name, parameter_types):
        raise Exception('should not be called')

    def try_coroutine_fuzzing(self):
        checker = CoroutineChecker(self.caller)
        if checker.is_coroutine():
            self.log('coroutine found')
            close_caller = SubsequentMethodCaller(self.caller, 'close')
            self.run_and_dump_code(close_caller)
            fuzzer = self.create_subsequent_method_fuzzer(self.caller, self.path, 'send', [ParameterType.any_object])
            fuzzer.run()

            # TODO: what does it expect in the third parameter? TracebackException?
            fuzzer = self.create_subsequent_method_fuzzer(self.caller, self.path, 'throw',
                                                          [ParameterType.exception_type, ParameterType.exception, ParameterType.any_object])
            fuzzer.run()

class BaseFunctionFuzzer(BaseFuzzer):

    def __init__(self, function, path = None):
        super().__init__(path)
        self.function = function
        self.path = path

    def skip(self):
        if self.function.has_no_parameters():
            self.log('function doesn\'t have parameters, skip')
            return True

        # TODO: add a command line option to specify excluded targets
        #       (os, and signal.pthread_kill should be excluded by default)
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

    # check if parameter types are correct
    # it tries to call specified function with correct values of its parameter types
    # returns true it the call suceeded
    def check_correct_parameter_type(self):
        self.log('check for correct parameter types')

        parameter_str = ''
        arg_number = 1
        for parameter_type in self.function.parameter_types:
            parameter_str += str(parameter_type)
            if arg_number != self.function.number_of_parameters():
                parameter_str +=  ', '
            arg_number = arg_number + 1

        self.log('number of parameters: {0:d}'.format(self.function.number_of_parameters()))
        self.log('parameter types: ' + parameter_str)

        caller = FunctionCaller(self.function)
        success = False
        try:
            caller.call()
            success = True
        except TypeError as err:
            self.log('warning: unexpected TypeError exception: {0}'.format(err))
            self.log('skip fuzzing')
        except AttributeError as err:
            self.log('warning: unexpected AttributeError exception: {0}'.format(err))
            self.log('looks like this API doesn\'t exist, quit')
        except ModuleNotFoundError as err:
            self.log('warning: unexpected ModuleNotFoundError exception: {0}'.format(err))
            self.log('looks like this module doesn\'t exist, quit')
        except Exception as err:
            # any other exception is considered as extected
            self.log('expected exception {0}: {1}'.format(type(err), err))
            success = True

        return success

    def run(self):
        if self.skip(): return
        self.log('try to fuzz function: ' + self.function.name)
        self.log('sources: ' + self.function.filename)

        # run actual fuzzing
        self.fuzz()

class LightFunctionFuzzer(BaseFunctionFuzzer):

    def __init__(self, function, path = None):
        super().__init__(function, path)

    def fuzz(self):
        # first, we try to call a target function with parameters of expected types
        # if this call succeeds, we can start fuzzing
        # while fuzzing, we fuzz each particular parameter,
        # but pass values of expected types to other parameters
        # this approach may help us to pass type checks of some parameters,
        # and reach more code in the target function
        if not self.check_correct_parameter_type():
            self.log('warning: skip, could not find correct parameter types for function: ' + self.function.name)
            return

        self.log('run light fuzzing for function: ' + self.function.name)
        arg_number = 1
        while arg_number <= self.function.number_of_parameters():
            for value in fuzzing_values:
                caller = FunctionCaller(self.function)
                caller.set_parameter_value(arg_number, value)
                self.dump.store(caller)
                try:
                    caller.call()
                    self.log('wow, it succeded')
                except Exception as err:
                    self.log('exception {0}: {1}'.format(type(err), err))
            arg_number = arg_number + 1

    def log(self, message):
        core.print_with_prefix('LightFunctionFuzzer', message)

class HardFunctionFuzzer(BaseFunctionFuzzer):

    def __init__(self, function, path = None):
        super().__init__(function, path)

    def fuzz(self):
        # first, we try to call a target function with parameters of expected types
        # if this call succeeds, we can start fuzzing
        # while fuzzing, we fuzz each particular parameter,
        # but pass values of expected types to other parameters
        # this approach may help us to pass type checks of some parameters,
        # and reach more code in the target function
        if not self.check_correct_parameter_type():
            self.log('warning: skip, could not find correct parameter types for function: ' + self.function.name)
            return

        self.log('run hard fuzzing for function: ' + self.function.name)
        caller = FunctionCaller(self.function)
        self.fuzz_hard(caller, 1, caller.function.number_of_parameters())

    def fuzz_hard(self, caller, current_arg_number, number_of_parameters):
        if current_arg_number == number_of_parameters:
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.dump.store(caller)
                try:
                    caller.call()
                    self.log('wow, it succeded')
                except Exception as err:
                    self.log('exception {0}: {1}'.format(type(err), err))
        else:
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.fuzz_hard(caller, current_arg_number + 1, number_of_parameters)

    def log(self, message):
        core.print_with_prefix('HardFunctionFuzzer', message)

# stops fuzzing when it finds a set of parameters which results to successful call
class CorrectParametersFuzzer(BaseFuzzer):

    def __init__(self, caller, path = None):
        super().__init__(path)
        self.caller = caller
        self.found = False

    def success(self):      return self.found
    def get_caller(self):   return self.caller

    def run(self):
        if self.caller.target().number_of_parameters() <= 1: return
        self.log('look for correct parameters for: ' + self.caller.target().name)
        self.search(self.caller, 1, self.caller.target().number_of_parameters())

    def search(self, caller, current_arg_number, number_of_parameters):
        if self.found: return
        if current_arg_number == number_of_parameters:
            if self.could_set_default_value(caller, current_arg_number):
                if self.could_make_successful_call(caller): return
            else:
                for value in general_parameter_values:
                    caller.set_parameter_value(current_arg_number, value)
                    if self.could_make_successful_call(caller): return
        else:
            if self.could_set_default_value(caller, current_arg_number):
                self.search(caller, current_arg_number + 1, number_of_parameters)
            else:
                for value in general_parameter_values:
                    caller.set_parameter_value(current_arg_number, value)
                    self.search(caller, current_arg_number + 1, number_of_parameters)
                    if self.found: return

    def could_set_default_value(self, caller, current_arg_number):
        if self.caller.target().has_default_value(current_arg_number):
            value = self.caller.target().get_default_value(current_arg_number)
            caller.set_parameter_value(current_arg_number, value)
            return True
        else: return False

    def could_make_successful_call(self, caller):
        self.found = self.run_and_dump_code(caller)
        if self.found:
            self.log('found correct parameter values: {0}'.format(caller.get_parameter_values()))
            return True
        else: return False

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

    def __init__(self, function, path = None):
        super().__init__(function, path)

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
        super().__init__(path)
        self.clazz = clazz
        self.path = path
        self.excludes = excludes

    def run(self):
        self.log('try to fuzz class: ' + self.clazz.name)
        self.log('sources: ' + self.clazz.filename)

        # make sure that we can call a constructor,
        # and get an instance of the class
        # if we can't, we can't continue fuzzing
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

    def __init__(self, method, constructor_caller, path = None, excludes = None):
        super().__init__(path)
        self.method = method
        self.constructor_caller = constructor_caller
        self.path = path
        self.excludes = excludes

    def run(self):
        if self.skip(self.method): self.log('skip fuzzing of ' + self.method.fullname())
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
        for parameter_index in range(1, self.method.number_of_parameters()+1):
            caller = successful_caller.clone()
            for value in fuzzing_values:
                caller.set_parameter_value(parameter_index, value)
                self.run_and_dump_code(caller)

    # TODO: move it to BaseFuzzer
    def skip(self, target):
        if self.excludes:
            if isinstance(self.excludes, list):
                for exclude in self.excludes:
                    if exclude in target.fullname():
                        return True
            else:
                if self.excludes in target.fullname():
                    return True

        return False

    def log(self, message):
        core.print_with_prefix('SmartMethodFuzzer', message)

    def warn(self, message):
        self.log('warning: {0:s}'.format(message))

# TODO: the code below is not used anymore, but coroutine fuzzing should be implemented

class LightMethodFuzzer(BaseFuzzer):

    def __init__(self, method, constructor_caller, fuzz_coroutine = True, path = None):
        super().__init__(path)
        self.method = method
        self.constructor_caller = constructor_caller
        self.fuzz_coroutine = fuzz_coroutine
        self.path = path

    def create_caller(self):
        return MethodCaller(self.method, self.constructor_caller)

    def get_number_of_parameters(self):
        return self.method.number_of_parameters()

    def run(self):
        if self.get_number_of_parameters() == 0:
            self.log('method doesn\'t have parameters, just call it')
            caller = self.create_caller()
            self.run_and_dump_code(caller)
            if self.fuzz_coroutine:
                LightCoroutineFuzzer(caller, self.path).run()
        else:
            arg_number = 1
            while arg_number <= self.get_number_of_parameters():
                for value in fuzzing_values:
                    caller = self.create_caller()
                    caller.set_parameter_value(arg_number, value)
                    self.run_and_dump_code(caller)
                    if self.fuzz_coroutine:
                        LightCoroutineFuzzer(caller, self.path).run()
                arg_number = arg_number + 1

    def log(self, message):
        core.print_with_prefix('LightMethodFuzzer', message)

class HardMethodFuzzer(BaseFuzzer):

    def __init__(self, method, constructor_caller, fuzz_coroutine = True, path = None):
        super().__init__(path)
        self.method = method
        self.constructor_caller = constructor_caller
        self.fuzz_coroutine = fuzz_coroutine
        self.path = path

    def create_caller(self):
        return MethodCaller(self.method, self.constructor_caller)

    def get_number_of_parameters(self):
        return self.method.number_of_parameters()

    def run(self):
        if self.get_number_of_parameters() == 0:
            self.log('method doesn\'t have parameters, just call it')
            caller = self.create_caller()
            self.run_and_dump_code(caller)
            if self.fuzz_coroutine:
                HardCoroutineFuzzer(caller, self.path).run()
        else:
            caller = self.create_caller()
            self.fuzz_hard(caller, 1)

    def fuzz_hard(self, caller, current_arg_number):
        if current_arg_number == self.get_number_of_parameters():
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.run_and_dump_code(caller)
                if self.fuzz_coroutine:
                    HardCoroutineFuzzer(caller, self.path).run()
        else:
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.fuzz_hard(caller, current_arg_number + 1)

    def log(self, message):
        core.print_with_prefix('HardMethodFuzzer', message)

class LightCoroutineFuzzer(BaseFuzzer):

    def __init__(self, caller, path = None):
        super().__init__(path)
        self.caller = caller
        self.path = path

    def create_subsequent_method_fuzzer(self, caller, path, method_name, parameter_types):
        return LightSubsequentMethodFuzzer(caller, path, method_name, parameter_types)

    def run(self):
        self.try_coroutine_fuzzing()

    def log(self, message):
        core.print_with_prefix('LightCoroutineFuzzer', message)

class HardCoroutineFuzzer(BaseFuzzer):

    def __init__(self, caller, path = None):
        super().__init__(path)
        self.caller = caller
        self.path = path

    def create_subsequent_method_fuzzer(self, caller, path, method_name, parameter_types):
        return HardSubsequentMethodFuzzer(caller, path, method_name, parameter_types)

    def run(self):
        self.try_coroutine_fuzzing()

    def log(self, message):
        core.print_with_prefix('HardCoroutineFuzzer', message)

class LightSubsequentMethodFuzzer(LightMethodFuzzer):

    def __init__(self, base_caller, path, subsequent_method_name, parameter_types = []):
        super().__init__(base_caller.method, base_caller.constructor_caller, False, path)
        self.base_caller = base_caller
        self.subsequent_method_name = subsequent_method_name
        self.parameter_types = parameter_types

    def create_caller(self):
        return SubsequentMethodCaller(self.base_caller, self.subsequent_method_name, self.parameter_types)

    def get_number_of_parameters(self):
        return len(self.parameter_types)

    def log(self, message):
        core.print_with_prefix('LightSubsequentMethodFuzzer', message)

class HardSubsequentMethodFuzzer(HardMethodFuzzer):

    def __init__(self, base_caller, path, subsequent_method_name, parameter_types = []):
        super().__init__(base_caller.method, base_caller.constructor_caller, False, path)
        self.base_caller = base_caller
        self.subsequent_method_name = subsequent_method_name
        self.parameter_types = parameter_types

    def create_caller(self):
        return SubsequentMethodCaller(self.base_caller, self.subsequent_method_name, self.parameter_types)

    def get_number_of_parameters(self):
        return len(self.parameter_types)

    def log(self, message):
        core.print_with_prefix('HardSubsequentMethodFuzzer', message)
