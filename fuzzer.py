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

# TODO: move it to BaseFuzzer
fuzzing_values = ('42', '42.3', 'True', 'False', '()', '[]', '{}', 'bytes()',
                  'bytearray()', '\'ololo\'', 'frozenset()', 'set()',
                  'Exception', 'Exception()',
                  ParameterValue('A()', 'class A: pass'))

class BaseFunctionFuzzer:

    def __init__(self, function, path = None):
        self.function = function
        self.dump = TestDump(path)

    def skip(self):
        if self.function.number_of_parameters() == 0:
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

        if self.function.module == 'signal':
            self.log('skip \'signal\' module')
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

        # first, we try to call a target function with parameters of expected types
        # if this call succeds, we can start fuzzing
        # while fuzzing, we fuzz each particular parameter,
        # but pass values of expected types to other parameters
        # this approach may help us to pass type checks of some parameters,
        # and reach more code in the target function

        if not self.check_correct_parameter_type():
            return

        # run actual fuzzing
        self.fuzz()

class LightFunctionFuzzer(BaseFunctionFuzzer):

    def __init__(self, function, path = None):
        super.__init__(function, path)

    def fuzz(self):
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
        super.__init__(function, path)

    def fuzz(self):
        self.log('run hard fuzzing for function: ' + self.function.name)
        caller = FunctionCaller(self.function)
        self.fuzz_hard(caller, 1)

    def fuzz_hard(self, caller, current_arg_number):
        if current_arg_number == caller.function.number_of_parameters():
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
                self.fuzz_hard(caller, current_arg_number + 1)

    def log(self, message):
        core.print_with_prefix('HardFunctionFuzzer', message)

# TODO: split it to LightClassFuzzer and HardClassFuzzer
class ClassFuzzer:

    def __init__(self, clazz, path = None, excludes = None):
        self.clazz = clazz
        self.path = path
        self.dump = TestDump(path)
        self.excludes = excludes

    def run(self, mode = 'light'):
        self.log('try to fuzz class: ' + self.clazz.name)
        self.log('sources: ' + self.clazz.filename)

        # make sure that we can call a constructor,
        # and get an instance of the class
        # if we can't, we can't continue fuzzing

        constructor_caller = self.get_constructor_caller()
        if constructor_caller == None:
            return

        if mode == 'light':
            self.run_light_fuzzing(constructor_caller)
        elif mode == 'hard':
            self.run_hard_fuzzing(constructor_caller)
        else:
            raise Exception('Unknown fuzzing mode: ' + mode)

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

    def get_constructor_caller(self):
        self.log('try to create an instance of ' + self.clazz.name)

        caller = ConstructorCaller(self.clazz)
        try:
            caller.call()
            self.log('successfully created an instance of ' + self.clazz.name)
            return caller
        except Exception as err:
            self.log('warning: exception: {0}'.format(err))
            self.log('couldn\'t create an instance of {0:s}'.format(self.clazz.name))
            self.log('skip fuzzing')
            return None

    def run_light_fuzzing(self, constructor_caller):
        self.log('run light fuzzing for class: ' + self.clazz.name)
        for method_name in self.clazz.methods:
            if method_name == '__init__': continue

            method = self.clazz.methods[method_name]
            if self.skip(method): continue
            self.log('try to fuzz method: ' + method.name)

            fuzzer = LightMethodFuzzer(
                method, constructor_caller, fuzz_coroutine = True, path = self.path)
            fuzzer.run()

    def run_hard_fuzzing(self, constructor_caller):
        self.log('run hard fuzzing for class: ' + self.clazz.name)
        for method_name in self.clazz.methods:
            if method_name == '__init__': continue

            method = self.clazz.methods[method_name]
            if self.skip(method): continue
            self.log('try to fuzz method: ' + method.name)

            fuzzer = HardMethodFuzzer(
                method, constructor_caller, fuzz_coroutine = True, path = self.path)
            fuzzer.run()

    def log(self, message):
        core.print_with_prefix('ClassFuzzer', message)

# base class for fuzzers, contains common methods
class BaseFuzzer:

    def __init__(self, path = None):
        self.dump = TestDump(path)

    def run_and_dump_code(self, caller):
        self.dump.store(caller)
        try:
            caller.call()
            self.log('wow, it succeded')
        except Exception as err:
            self.log('exception {0}: {1}'.format(type(err), err))
        Stats.get().increment_tests()

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
