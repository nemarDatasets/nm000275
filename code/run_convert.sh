#!/bin/bash
# Orchestrate: convert -> finalize -> validate. Run from driving_eeg/.
set -e
cd /expanse/lustre/projects/csd403/bpinto/driving_eeg
PY="/tmp/claude-540910/venv/bin/python"
# Cap virtual-memory footprint to fit the 8GB login-node ulimit -v:
# single-thread BLAS + few glibc malloc arenas keep address space small.
MEMENV="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MALLOC_ARENA_MAX=2"
RUN="env -i HOME=/home/bpinto PYTHONDONTWRITEBYTECODE=1 $MEMENV $PY -u"

echo "############ STEP 1: convert .set -> BIDS ############"
$RUN convert_to_bids.py

echo "############ STEP 2: finalize metadata ############"
$RUN finalize_bids.py

echo "############ STEP 3: bids-validator ############"
export PATH="/home/bpinto/.bun/bin:$PATH"
export BUN_INSTALL_CACHE_DIR=/tmp/claude-540910/buncache
bunx --bun bids-validator@latest bids --verbose 2>&1 | tail -60 || true

echo "ALL DONE"
