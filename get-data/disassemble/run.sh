#!/usr/bin/env bash

NUM_INSTANCES=1
PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DATASET_DIR=$PARENT_DIR/../../../UnderstandableBinary-data
SCRIPT_LOG_DIR=$PARENT_DIR/../../local/ghidra-logs
GHIDRA_DIR=$PARENT_DIR/ghidra
GHIDRA_SCRIPT_NAME="BatchDecompile.java"
# Ghidra uses 'false' and 'true' instead of '0' and '1'
IMPORT_EXISTING_FILES=false
DECOMPILE_EXISTING_FILES=false
SKIP_SUCCESSES=true
SKIP_FAILURES=false
STATS_DIR=""

# Show help if necessary
function show_help() {
  usage="Usage: $0 [-o DATASET_DIR] [-w STATS_DIR] [-l SCRIPT_LOG_DIR] [-j NUM_INSTANCES] [-s | -f | -F]

Disassemble object files (.o) in DATASET_DIR using Ghidra, creating (.o.c) files and also Ghidra projects.
DATASET_DIR should contain subdirectories containing artifacts; each artifact is processed separately.

    -o DATASET_DIR    Directory where the dataset is stored. Default: $PARENT_DIR/../../../UnderstandableBinary-data
    -w STATS_DIR      Watch for new files (empty STATS_DIR/*.success files are markers) and decompile them.
                      This changes the mode so that Ghidra will only decompile *.success marked files.
                      However it will attempt to decompile old *.success files, overwriting if -f or -F is passed,
                      else skipping unless the file actually needs to be decompiled. Default: \"\" (no watch mode)
    -l SCRIPT_LOG_DIR Directory where the script logs are stored. Default: $PARENT_DIR/../../local/ghidra-logs
    -j NUM_INSTANCES  Number of processes to run in parallel, 0 for as many as possible. Default: 1
    -s                Skip decompiling failures as well as successes (successes skipped unless -f or -F). Default: false
    -f                Decompile existing files and redo successes but DO NOT reimport and reanalyze cached Ghidra files.
                      Default: false
    -F                Decompile existing files, redo successes, and DO reimport and reanalyze cached Ghidra files.
                      Default: false"
  echo "$usage"
}

# Process options
OPTIND=1
while getopts "h?o:w:l:j:sfF" opt; do
  case "$opt" in
    h|\?)
      show_help
      exit 0
      ;;
    o)  DATASET_DIR=$OPTARG
      ;;
    w)  STATS_DIR=$OPTARG
      ;;
    l)  SCRIPT_LOG_DIR=$OPTARG
      ;;
    j)  NUM_INSTANCES=$OPTARG
      ;;
    s)  SKIP_FAILURES=true
      ;;
    f)  DECOMPILE_EXISTING_FILES=true
        SKIP_SUCCESSES=false
      ;;
    F)  IMPORT_EXISTING_FILES=true
        DECOMPILE_EXISTING_FILES=true
        SKIP_SUCCESSES=false
      ;;
  esac
done
shift $((OPTIND-1))
[ "${1:-}" = "--" ] && shift

# Extract Ghidra dir if necessary
if [ ! -d "$GHIDRA_DIR" ]; then
    echo "Ghidra dir not found, unzipping (first time)"
    tar -xzf "$GHIDRA_DIR.tar.gz" -C "$GHIDRA_DIR"
fi

# Patch analyzeHeadless, increase heap size
# (do this even if already done just to be safe and not cause confusing errors)
sed -i '' 's/^MAXMEM=.*$/MAXMEM=6G/g' "$GHIDRA_DIR/support/analyzeHeadless"

# Create script log dir if necessary
if [ "$SCRIPT_LOG_DIR" != "" ]; then
  mkdir -p "$SCRIPT_LOG_DIR"
fi

# Preprocessing: extract every .a file so that we can process (we could also do this in the GhidraScript but it's easier in Bash)
echo "*** EXTRACTING .a FILES"
function preprocess_a() {
  apath=$1
  if [ "$apath" == "{}" ] ; then
    # Idk why this happens
    return
  fi
  if [ -d "$apath.extracted" ] ; then
    if [ "$IMPORT_EXISTING_FILES" == "false" ] ; then
      echo "** SKIPPING $apath (already extracted)"
      return
    else
      # Safe removal since we know its only 1 level deep
      rm "$apath.extracted/*"
      rmdir "$apath.extracted"
    fi
  fi
  echo "** EXTRACTING $apath"
  mkdir "$apath.extracted"
  cd "$apath.extracted" && ar -x "../$(basename "$apath")"
}
export IMPORT_EXISTING_FILES
export -f preprocess_a
find "$DATASET_DIR" -name "*.a" -print0 | xargs -0 -n 1 -P "$NUM_INSTANCES" -I {} bash -c 'preprocess_a "$@"' _ {}

# Processing logic (for each subdirectory)
function process_one() {
  artifactDir=$1

  if [ "$SKIP_SUCCESSES" == true ] && [ -f "$artifactDir/ghidra.success" ] ; then
    echo "*** SKIPPING $artifactDir (previously processed)"
    return
  elif [ "$SKIP_FAILURES" == true ] && [ -f "$artifactDir/ghidra.fail" ] ; then
    echo "*** SKIPPING $artifactDir (previously failed)"
    return
  fi

  echo "*** PROCESSING $artifactDir..."

  artifactName=$(basename "$artifactDir")
  if [ "$SCRIPT_LOG_DIR" != "" ]; then
    scriptLogFile="$SCRIPT_LOG_DIR/$artifactName.log"
  else
    scriptLogFile="/dev/null"
  fi

  "$GHIDRA_DIR/support/analyzeHeadless" \
    "$artifactDir" ghidra \
    -scriptPath "$PARENT_DIR" \
    -scriptLog "$scriptLogFile" \
    -preScript "$PARENT_DIR/$GHIDRA_SCRIPT_NAME" "$artifactDir" "$IMPORT_EXISTING_FILES" "$DECOMPILE_EXISTING_FILES" "$STATS_DIR"
  # shellcheck disable=SC2181
  exit=$?

  if [ $exit -gt 127 ]; then
    echo "*** ABORT: Decompiling $artifactDir exited with code $exit"
    exit 1
  elif [ $exit -ne 0 ]; then
    echo "*** ERROR: Decompiling $artifactDir exited with code $exit"
    touch "$artifactDir/ghidra.fail"
  else
    echo "*** SUCCESS decompiling $artifactDir!"
    touch "$artifactDir/ghidra.success"
  fi
}
export GHIDRA_DIR
export PARENT_DIR
export SCRIPT_LOG_DIR
export GHIDRA_SCRIPT_NAME
# export IMPORT_EXISTING_FILES
export DECOMPILE_EXISTING_FILES
export STATS_DIR
export SKIP_SUCCESSES
export SKIP_FAILURES
export -f process_one

# Process each subdirectory (artifact), but process $NUM_INSTANCES simultaneously
# `exec` also means that this must be the last command
echo "*** PROCESSING ALL IN $DATASET_DIR ($NUM_INSTANCES instances)"
find "$DATASET_DIR"/* -type d -prune -print0 |
  exec xargs -P "$NUM_INSTANCES" -0 -n 1 -I {} bash -c 'process_one "$@"' _ {}
