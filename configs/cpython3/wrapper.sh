#!/usr/bin/env bash

if [ "x${DEBUG}" = "xyes" ]; then
    echo "ssh is ready, we'are waiting for you ..."
    /usr/sbin/sshd -D
else
    bash /var/src/pyconfusion/scripts/fuzz_modules.sh
fi
