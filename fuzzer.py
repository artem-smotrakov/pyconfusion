#!/usr/bin/python

import textwrap
import os
import core

from core import ParameterType
from core import FunctionCaller

class FunctionFuzzer:

    def __init__(self, function):
        self.function = function

    def run(self):
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

        if not self.check_correct_parameter_type(): return

        self.log('start fuzzing')

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
        except ValueError as err:
            self.log('warning: unexpected ValueError exception: {0}'.format(err))
        except AttributeError as err:
            self.log('warning: unexpected AttributeError exception: {0}'.format(err))
        except ModuleNotFoundError as err:
            self.log('warning: unexpected ModuleNotFoundError exception: {0}'.format(err))
        except Exception as err:
            # any other exception is considered as extected
            self.log('expected exception {0}: {1}'.format(type(err), err))
            success = True

        if success:
            self.log('good to start fuzzing')
            return True
        else:
            self.log('couldn\' call function successfully, skip fuzzing')
            return False

    def log(self, message):
        core.print_with_prefix('FunctionFuzzer', message)
