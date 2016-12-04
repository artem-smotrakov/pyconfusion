#!/usr/bin/python

import textwrap
import os

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

# contains fuzzer configuration
# all parameters can be accessed as attributes
class Task:

    # read arguments returned by argparse.ArgumentParser
    def __init__(self, args):
        self.args = vars(args)

    def __getattr__(self, name):
        return self.args[name]

    def run(self):
        if self.args['mode'] == 'targets':
            if self.args['src'] == None:
                raise Exception('Sources not specified')
            finder = TargetFinder(self.args['src'])
            finder.run()
        else:
            raise Exception('Unknown mode: ' + self.args['mode'])

class TargetFinder:

    def __init__(self, directory):
        self.directory = directory

    def run(self):
        for root, dirs, files in os.walk(self.directory):
            for file in files:
                # TODO: should it look for .h files as well?
                if file.endswith(".c"):
                    print(os.path.join(root, file))
