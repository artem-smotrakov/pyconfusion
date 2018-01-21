#!/bin/bash

EXCLUDE_LIST=${EXCLUDE_LIST:-"exclude_list"}
FUZZED_MODULES=${FUZZED_MODULES:-"fuzzed_modules"}
MODULES=${MODULES:-"modules"}
LOGS=${LOGS:-"."}
MODULE=${MODULE:-""}

fuzz() {
  module=${1}
  echo "fuzz ${module}"

  ASAN_OPTIONS="detect_leaks=0 allocator_may_return_null=1" \
    ${PYTHON} \
      ${WS}/pyconfusion.py \
        --command fuzzer \
        --modules ${module} \
        --exclude ${EXCLUDE_LIST} > ${LOGS}/${module}.log 2>&1

  if [ $? -ne 0 ]; then
    echo "game over"
    exit 1
  fi
}

if [ "x${MODULE}" = "x" ]; then
  for module in `cat ${MODULES}`
  do
    if grep -Fx ${module} ${FUZZED_MODULES} > /dev/null 2>&1; then
       continue
     fi

    fuzz ${module}
    echo ${module} >> ${FUZZED_MODULES}
  done
else
  fuzz ${MODULE}
fi
