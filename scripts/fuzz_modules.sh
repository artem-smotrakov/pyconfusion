#!/bin/bash

for module in `cat modules`
do
  if grep -Fx ${module} fuzzed_modules > /dev/null 2>&1; then
     continue
  fi

  echo "fuzz ${module}"

  ASAN_OPTIONS="detect_leaks=0 allocator_may_return_null=1" \
    ${PYTHON} \
      ${WS}/pyconfusion.py \
        --command fuzzer \
        --modules ${module} \
        --exclude `cat exclude_list` > ${module}.log 2>&1

  if [ $? -ne 0 ]; then
    echo "game over"
    break
  fi

  echo ${module} >> fuzzed_modules
done
