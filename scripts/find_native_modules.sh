#!/bin/bash

ASAN_OPTIONS="detect_leaks=0 allocator_may_return_null=1" \
  ${PYTHON} \
    ${WS}/pyconfusion.py \
      --src ${SRC} \
      --command targets \
        | grep "found module" | cut -d ":" -f 2 | sed 's/^ *//;s/ *$//'
