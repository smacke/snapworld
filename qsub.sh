#!/bin/sh

PPN=18

NODES=`seq -f "iln%02g.stanford.edu:ppn=${PPN}" -s "+" 1 17`

CMD="qsub -I -l nodes=${NODES}"

echo $CMD

$CMD
