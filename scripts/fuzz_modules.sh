#!/bin/bash

EXCLUDE_LIST=${EXCLUDE_LIST:-"exclude_list"}
FUZZED_MODULES=${FUZZED_MODULES:-"fuzzed_modules"}
MODULES=${MODULES:-"modules"}
LOGS=${LOGS:-"."}
for module in `cat ${MODULES}`
do
  if grep -Fx ${module} ${FUZZED_MODULES} > /dev/null 2>&1; then
     continue
  fi

  echo "fuzz ${module}"

  ASAN_OPTIONS="detect_leaks=0 allocator_may_return_null=1" \
    ${PYTHON} \
      ${WS}/pyconfusion.py \
        --command fuzzer \
        --modules ${module} \
        --exclude `cat ${EXCLUDE_LIST}` > ${LOGS}/${module}.log 2>&1

  if [ $? -ne 0 ]; then
    echo "game over"
    break
  fi

  echo ${module} >> ${FUZZED_MODULES}
done
