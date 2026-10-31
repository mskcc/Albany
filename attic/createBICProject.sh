#!/bin/bash

SDIR="$( cd "$( dirname "$0" )" && pwd )"
PDIR=$(basename $PWD | sed 's/Proj_//')
DDIR=$(basename $(dirname $PWD))

echo $DDIR, $PDIR

$SDIR/getProjectFiles.py $PDIR

if [ "$DDIR" == "chipseq" ]; then

    Rscript --no-save $SDIR/makeChIPSeqProject.R *yaml

elif [ "$DDIR" == "variant" ]; then

    Rscript --no-save $SDIR/makeVariantProject.R *yaml

else

    echo "Unknown pipeline ["$DDIR"]"
    exit

fi