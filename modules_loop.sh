#!/bin/bash

for module in `echo ${MODULES} | sed 's/,/\n/g'`
do
    if echo ${module} | grep '#' > /dev/null 2>&1 ; then
        echo "skip ${module}"
        continue
    fi
    bash MODULES=${module} fuzz_module.sh > ${module}.log 2>&1
done
