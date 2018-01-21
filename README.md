# PyConfusion

## What is PyConfusion?

PyConfusion is a tool for negative testing of Python API such as functions and methods. PyConfusion invokes function and methods with incorrect and unexpected parameters which may uncover bugs. In other words, PyConfusion works as an API fuzzer. For example, let's assume that we have `foo` function which takes two parameters, and expect the first one to be a string, and the second one to be an integer. PyConfusion is going to run `foo` function with different combinations of parameters such as `('string', [])`, `(1.2, ()`), `(1, "x" * 2 ** 20`) and so on. 

Currently PyConfusion is good to use with functions and methods whcih are implemented in C/C++. If `foo` is implemented in C/C++, and doesn't properly check for input values before using them, then unexpected parameters may trigger type confusions, memory corruptions, and other issues which may affect C/C++ code.

## Command line options

PyConfusion has two modes:

* Analyze sources, and look for functions and methods which are implemented in C (see `--command targets` command line option below)
* Run testing for specified modules (see `--command fuzzer` and `--modules` command line options below)

`--help` option prints all available command line paramenters:

```
$ python3 pyconfusion.py --help
usage: pyconfusion.py [-h] [--src SRC] [--command {targets,fuzzer}]
                      [--fuzzer_filter FUZZER_FILTER]
                      [--finder_filter FINDER_FILTER] [--out OUT]
                      [--exclude EXCLUDE] [--modules MODULES]
                      [--fuzzing_data FUZZING_DATA]

optional arguments:
  -h, --help            show this help message and exit
  --src SRC             path to sources
  --command {targets,fuzzer}
                        what do you want to do?
  --fuzzer_filter FUZZER_FILTER
                        target filter for fuzzer
  --finder_filter FINDER_FILTER
                        file filter for finder
  --out OUT             path to directory for generated tests
  --exclude EXCLUDE     comma-separated list of objects to exclude or path to
                        exclude list
  --modules MODULES     comma-separated list of modules to fuzz or path to
                        file with modules
  --fuzzing_data FUZZING_DATA
                        a script which provides data for fuzzing
```

## Running PyConfusion with CPython

PyConfusion can be run with CPython. First, PyConfusion can look for modules which contain functions and methods implemented in C:

```
python3 pyconfusion.py --src /path/to/cpython/sources --command targets
```

It's going to print something like the following:

```
[TargetFinder] parse file: /home/artem/projects/python/src/cpython-asan/Modules/_io/_iomodule.c
[TargetFinder] found module: io
[TargetFinder] found class: BlockingIOError
...
[TargetFinder] found a method with 1 parameters: io.StringIO.read
[TargetFinder] found a method with no parameters: io.StringIO.readable
[TargetFinder] found a method with 1 parameters: io.StringIO.readline
[TargetFinder] found a method with 1 parameters: io.StringIO.readlines
[TargetFinder] found a method with 2 parameters: io.StringIO.seek
[TargetFinder] found a method with no parameters: io.StringIO.seekable
[TargetFinder] found a method with no parameters: io.StringIO.tell
[TargetFinder] found a method with 1 parameters: io.StringIO.truncate
[TargetFinder] found a method with no parameters: io.StringIO.writable
[TargetFinder] found a method with 1 parameters: io.StringIO.write
[TargetFinder] found a method with 1 parameters: io.StringIO.writelines
...
```

If you'd like to find all modules which contains APIs implemented in C, then you can use something like the following:

```
python3 pyconfusion.py --src /path/to/cpython/sources --command targets | grep "found module" | cut -d ":" -f 2 | sed 's/^ *//;s/ *$//'
```

PyConfusion can test modules which were found in CPython sources:

```
/path/to/bin/python3 pyconfusion.py --src /path/to/sources --command fuzzer
```

Note that `/path/to/bin/python3` should be built from the sources in `/path/to/sources`. Otherwise, the results may be unexpected.

## Running PyConfusion with any Python module

PyConfusion can be run with any module. First, it's going to try to discover available functions, classes and methods. Then, it's going to fuzz them. Here is a coupld of examples:

```
# test '_io' module
python3 pyconfusion.py --command fuzzer --modules _io

# test '_io' and '_json' modules
python3 pyconfusion.py --command fuzzer --modules "_io,_json"

# tests modules listed in a file
python3 pyconfusion.py --command fuzzer --modules /path/to/module/list
```

## Run PyConfusion in a Docker container

TBD

## PyConfusion and AddressSanitizer

TBD

## What's next?

TBD don't look only for crashes, but analyse outputs
