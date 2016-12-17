#!/bin/bash

PYTHON=${1:-"python"}
TESTS=${2:-"./"}

# disable memory leaks checker
export ASAN_OPTIONS="${ASAN_OPTIONS} detect_leaks=0"

for TEST in `ls ${TESTS}`
do
    echo "run ${TEST}"
    ${PYTHON} ${TEST} > log 2>&1

    if grep "AddressSanitizer" log > /dev/null 2>&1; then
        echo "ASan found something, game over"
        break
    fi

    if grep -i "segmentation fault" log > /dev/null 2>&1; then
        echo "Segmentation fault, game over"
        break
    fi
done
