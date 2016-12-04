#!/usr/bin/python

import textwrap
import os
import core

from core import ParameterType

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
        self.log('number of parameters: {0:d}'.format(self.function.number_of_parameters()))

        code = 'import ' + self.function.module + '\n'
        parameters = ''
        arg_number = 1
        parameter_str = ''
        for parameter_type in self.function.parameter_types:
            parameter_str += str(parameter_type) + ', '
            parameter_name = 'arg' + str(arg_number)
            value = self.default_value(parameter_type)
            code += '{0:s} = {1:s}\n'.format(parameter_name, value)
            if arg_number == self.function.number_of_parameters():
                parameters += parameter_name
            else:
                parameters += parameter_name + ', '
            arg_number = arg_number + 1

        code += '{0:s}({1:s})\n'.format(self.function.name, parameters)

        parameter_str = parameter_str.strip(', ')
        self.log('parameter types: ' + parameter_str)

        self.log('run the following code:\n\n' + code)
        success = False
        try:
            exec(code)
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

    def default_value(self, parameter_type):
        if parameter_type == ParameterType.byte_like_object:
            return 'bytes()'
        if parameter_type == ParameterType.integer:
            return '42'
        if parameter_type == ParameterType.any_object:
            # TODO: anything better?
            return '()'

        # TODO: anything better?
        return '()'
