#!/bin/bash

EXCLUDE_LIST=${EXCLUDE_LIST:-"_testcapi"}
ASAN_OPTIONS="detect_leaks=0" \
    ${PYTHON} \
        pyconfusion.py \
            --command fuzzer \
            --exclude ${EXCLUDE_LIST} \
            --modules ${MODULES} \
