#!/bin/bash

PYTHON=${1:-"python"}
TESTS=${2:-"./"}
OPTIONS=${3:-""}

# disable memory leaks checker
export ASAN_OPTIONS="${ASAN_OPTIONS} detect_leaks=0"

for TEST in `find ${TESTS} -name "*.py"`
do
    echo "run ${TEST}"
    ${PYTHON} ${OPTIONS} ${TEST} > log 2>&1

    if [ $? -eq 139 ]; then
        echo "Segmentation fault, game over"
        break
    fi

    if grep "AddressSanitizer" log > /dev/null 2>&1; then
        echo "ASan found something, game over"
        break
    fi
done
