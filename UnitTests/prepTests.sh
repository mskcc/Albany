#!/bin/bash

#
# ./prepTests.sh <(cat mappingFiles  | fgrep -vwf tested | tail -25 | xargs wc -l | sort -nr | tail -15 | awk '{print $2}')
#

for file in $(cat $1); do
    echo $(basename $file);
    cat $file | sort -V >$(basename $file).srtV;
done

Rscript --no-save fixMappingIDs.R Proj_*srtV

