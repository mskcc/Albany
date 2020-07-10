#!/bin/bash

diff='/juno/work/bic/socci/opt/bin/diff --color=auto'
DS=$(date +%y.%m.%d)

LOGFILE="log_unitTest01"_${DS}
rm $LOGFILE

for mapfile in Targets/*_sample_mapping.txt*; do

    projNo=$(basename $mapfile | sed 's/.*Proj_//' | sed 's/_sample_mapping.*//')

    echo -n "Testing ..." $projNo | tee -a $LOGFILE

    python3 ../getProjectFiles.py $projNo >/dev/null
    cat Proj_${projNo}_sample_mapping.txt | sort -V >srt
    mv srt Proj_${projNo}_sample_mapping.txt

    echo -n " " | tee -a $LOGFILE

    DIFF=$(diff $mapfile Proj_${projNo}_sample_mapping.txt)

    if [ "$DIFF" != "" ]; then
        echo "FAILED" | tee -a $LOGFILE
        $diff -u --color $mapfile Proj_${projNo}_sample_mapping.txt | tee -a $LOGFILE
        echo | tee -a $LOGFILE
        echo | tee -a $LOGFILE
    else
        #rm Proj_${projNo}_sample_mapping.txt
        echo "PASSED" | tee -a $LOGFILE
        rm Proj_${projNo}_sample_mapping.txt
    fi

    rm *_metadata.yaml

done

