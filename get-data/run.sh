#!/usr/bin/env bash

NUM_GHIDRA_INSTANCES=2
PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DATASET_DIR=$PARENT_DIR/../../../UnderstandableBinary-data
GHIDRA_SCRIPT_LOG_DIR=$PARENT_DIR/../local/ghidra-logs
NUM_PACKAGES=4294967295
RECREATE=0

# Show help if necessary
function show_help() {
  usage="Usage: $0 [-o DATASET_DIR] [-n NUM_PACKAGES] [-l GHIDRA_SCRIPT_LOG_DIR] [-j NUM_GHIDRA_INSTANCES] [-f] [-F]

Create the dataset by downloading and building packages, then decompile using Ghidra.

    -o DATASET_DIR             Directory where the dataset is installed. Default: $DATASET_DIR
    -n NUM_PACKAGES            Number of packages to install from each repo (so we actually do x3 this). Default: all
    -l GHIDRA_SCRIPT_LOG_DIR   Directory where the Ghidra script logs are stored. Default: $GHIDRA_SCRIPT_LOG_DIR
    -j NUM_GHIDRA_INSTANCES    Number of Ghidra instances to run in parallel from each repo (so we actually do up to 3x
                               this). Default: $NUM_GHIDRA_INSTANCES
    -f                         Recreate the entire dataset.
                               Otherwise we will resume and skip already-processed (e.g. if it exited early) Default: false"
  echo "$usage"
}

# Process options
OPTIND=1
while getopts "h?j:o:n:l:f:" opt; do
  case "$opt" in
    h|\?)
      show_help
      exit 0
      ;;
    j)  NUM_GHIDRA_INSTANCES=$OPTARG
      ;;
    o)  DATASET_DIR=$OPTARG
      ;;
    n)  NUM_PACKAGES=$OPTARG
      ;;
    l)  GHIDRA_SCRIPT_LOG_DIR=$OPTARG
      ;;
    f)  RECREATE=1
      ;;
  esac
done
shift $((OPTIND-1))
[ "${1:-}" = "--" ] && shift

# *don't* remove the entire directory if -f, because we instead pass to children, because we also need to remove the docker container
if [ "$RECREATE" -eq 1 ]; then
  FORCE="-f"
else
  FORCE=""
fi

# Create the dataset directory if it doesn't exist
if [ ! -d "$DATASET_DIR" ]; then
  mkdir -p "$DATASET_DIR"
fi

# Run everything simultaneously, and run Ghidra in watch mode (Ghidra doesn't need to force because it will only process new files)
(
  "$PARENT_DIR/apt/run.sh" -o "$DATASET_DIR/apt" -n "$NUM_PACKAGES" "$FORCE";
  "$PARENT_DIR/ghidra/run.sh" -o "$DATASET_DIR/apt" -n "$NUM_PACKAGES" -l "$GHIDRA_SCRIPT_LOG_DIR" -j "$NUM_GHIDRA_INSTANCES"
) &
(
  "$PARENT_DIR/vcpkg/run.sh" -o "$DATASET_DIR/vcpkg" -n "$NUM_PACKAGES" "$FORCE";
  "$PARENT_DIR/ghidra/run.sh" -o "$DATASET_DIR/vcpkg/buildtrees" -n "$NUM_PACKAGES" -l "$GHIDRA_SCRIPT_LOG_DIR" -j "$NUM_GHIDRA_INSTANCES"
) &
(
  "$PARENT_DIR/conan/run.sh" -o "$DATASET_DIR/conan" -n "$NUM_PACKAGES" "$FORCE";
  "$PARENT_DIR/ghidra/run.sh" -o "$DATASET_DIR/conan/data" -n "$NUM_PACKAGES" -l "$GHIDRA_SCRIPT_LOG_DIR" -j "$NUM_GHIDRA_INSTANCES"
) &
