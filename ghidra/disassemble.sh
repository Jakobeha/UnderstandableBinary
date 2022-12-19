#!/usr/bin/env bash

PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DATASET_DIR=${PARENT_DIR}/../local/dataset
GHIDRA_DIR=${PARENT_DIR}/latest_release
GHIDRA_SCRIPT_NAME="BatchDecompile.java"
# TIMEOUT=1800000
IMPORT_EXISTING_FILES=0
ANALYZE_EXISTING_FILES=0

# We cannot reliably catch HeapOutOfMemoryError, so we need to repeat running this until we get a signal that we're done
# But also we have RESTART_LIMIT in case there is a real error which causes no progress
echo "*** PROCESSING ALL IN ${DATASET_DIR}"
for artifactDir in "${DATASET_DIR}"/*; do
  echo "*** PROCESSING ${artifactDir}..."
  "${GHIDRA_DIR}/support/analyzeHeadless" \
    "${artifactDir}" ghidra \
    -scriptPath "${PARENT_DIR}" \
    -preScript "${PARENT_DIR}/${GHIDRA_SCRIPT_NAME}" "${artifactDir}" "${IMPORT_EXISTING_FILES}" "${ANALYZE_EXISTING_FILES}"
done