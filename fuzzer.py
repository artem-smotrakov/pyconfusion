#!/usr/bin/python

import textwrap
import os
import core

from core import ParameterType
from core import ParameterValue
from core import FunctionCaller
from core import MethodCaller
from core import ConstructorCaller

fuzzing_values = ('42', '42.3', 'True', 'False', '()', '[]', '{}', 'bytes()',
                  'bytearray()', '\'ololo\'', 'frozenset()', 'set()',
                  ParameterValue('A()', 'class A: pass'))

class FunctionFuzzer:

    def __init__(self, function):
        self.function = function

    def run(self, mode = 'light'):
        self.log('try to fuzz function: ' + self.function.name)
        self.log('sources: ' + self.function.filename)

        if self.function.number_of_parameters() == 0:
            self.log('function doesn\'t have parameters, skip')
            return

        # TODO: add a command line option to specify excluded targets
        #       (os, and signal.pthread_kill should be excluded by default)
        if self.function.module == 'os':
            self.log('skip \'os\' module')
            return

        if self.function.name == 'signal.pthread_kill':
            self.log('skip \'signal.pthread_kill()\' function')
            return

        if self.function.name == 'signal.sigwait':
            self.log('skip \'signal.sigwait()\' function')
            return

        if self.function.name == 'signal.sigwaitinfo':
            self.log('skip \'signal.sigwaitinfo()\' function')
            return

        # first, we try to call a target function with parameters of expected types
        # if this call succeds, we can start fuzzing
        # while fuzzing, we fuzz each particular parameter,
        # but pass values of expected types to other parameters
        # this approach may help us to pass type checks of some parameters,
        # and reach more code in the target function

        if not self.check_correct_parameter_type():
            return

        if mode == 'light':
            self.run_light_fuzzing()
        elif mode == 'hard':
            self.run_hard_fuzzing()
        else:
            raise Exception('Unknown fuzzing mode: ' + mode)

    def run_light_fuzzing(self):
        self.log('run light fuzzing for function: ' + self.function.name)
        arg_number = 1
        while arg_number <= self.function.number_of_parameters():
            for value in fuzzing_values:
                caller = FunctionCaller(self.function)
                caller.set_parameter_value(arg_number, value)
                try:
                    caller.call()
                    self.log('wow, it succeded')
                except Exception as err:
                    self.log('exception {0}: {1}'.format(type(err), err))
            arg_number = arg_number + 1

    def run_hard_fuzzing(self):
        self.log('run hard fuzzing for function: ' + self.function.name)
        caller = FunctionCaller(self.function)
        self.fuzz_hard(caller, 1)

    def fuzz_hard(self, caller, current_arg_number):
        if current_arg_number == caller.function.number_of_parameters():
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                try:
                    caller.call()
                    self.log('wow, it succeded')
                except Exception as err:
                    self.log('exception {0}: {1}'.format(type(err), err))
        else:
            for value in fuzzing_values:
                caller.set_parameter_value(current_arg_number, value)
                self.fuzz_hard(caller, current_arg_number + 1)

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

    def log(self, message):
        core.print_with_prefix('FunctionFuzzer', message)

class ClassFuzzer:

    def __init__(self, clazz):
        self.clazz = clazz

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
            method = self.clazz.methods[method_name]
            self.log('try to fuzz method: ' + method.name)

            if method.number_of_parameters() == 0:
                self.log('method doesn\'t have parameters, skip')
                continue

            arg_number = 1
            while arg_number <= method.number_of_parameters():
                for value in fuzzing_values:
                    caller = MethodCaller(method, constructor_caller)
                    caller.set_parameter_value(arg_number, value)
                    try:
                        caller.call()
                        self.log('wow, it succeded')
                    except Exception as err:
                        self.log('exception {0}: {1}'.format(type(err), err))
                arg_number = arg_number + 1

    def run_hard_fuzzing(self, constructor_caller):
        self.log('run hard fuzzing for class: ' + self.clazz.name)
        raise Exception('Not implemented yet')

    def log(self, message):
        core.print_with_prefix('ClassFuzzer', message)
