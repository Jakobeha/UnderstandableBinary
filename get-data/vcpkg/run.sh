#!/bin/bash

PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
INSTALL_DIR=$PARENT_DIR/../../../UnderstandableBinary-data/vcpkg
STATS_DIR=$INSTALL_DIR-stats
NUM_PACKAGES=4294967295
RECREATE=0

# Show help if necessary
function show_help() {
  usage="Usage: $0 [-o INSTALL_DIR] [-f]

Download and build packages from the vcpkg repository

    -n NUM_PACKAGES  Number of packages to install. Default: all
    -o INSTALL_DIR   Directory where the packages are installed. Default: $INSTALL_DIR
    -f               Recreate the vcpkg root, deleting old files. otherwise we will resume installing. Default: false"
  echo "$usage"
}

# Process options
OPTIND=1
while getopts "h?n:o:f" opt; do
  case "$opt" in
    h|\?)
      show_help
      exit 0
      ;;
    n)  NUM_PACKAGES=$OPTARG
      ;;
    o)  INSTALL_DIR=$OPTARG
      ;;
    f)  RECREATE=1
      ;;
  esac
done
shift $((OPTIND-1))
[ "${1:-}" = "--" ] && shift

echo "*** Using VCPKG_ROOT=$INSTALL_DIR"
export VCPKG_ROOT=$INSTALL_DIR

if [ -d "$INSTALL_DIR" ] && [ $RECREATE -eq 1 ]; then
    echo "*** Removing install dir and recreating"
    rm -rf "$INSTALL_DIR"
fi

if [ ! -d "$INSTALL_DIR" ]; then
  git clone https://github.com/microsoft/vcpkg "$INSTALL_DIR"
fi
mkdir -p "$STATS_DIR"

cd "$INSTALL_DIR" || exit 1

echo "*** Searching for packages to install"
vcpkg search | cut -d ' ' -f1 | tac | tail -n +2 | tac | head -n "$NUM_PACKAGES" > packages.txt

echo "*** Installing $(< packages.txt wc -l) packages"
NUM_SUCCESS=0
while read -r package; do
  if [ -f "$STATS_DIR/$package.failed" ]; then
    echo "** Skipping $package (failed before, num success=$NUM_SUCCESS)"
    continue
  elif [ -f "$STATS_DIR/$package.success" ]; then
    echo "** Skipping $package (already done, num success=$NUM_SUCCESS)"
    NUM_SUCCESS=$((NUM_SUCCESS + 1))
    continue
  fi
  echo "** vcpkg install $package (num success=$NUM_SUCCESS)"
  vcpkg install "$package" --allow-unsupported
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
    echo "** Failed to install $package"
    # Write file so that we skip in subsequent calls
    touch "$STATS_DIR/$package.failed"
    continue
  fi
  touch "$STATS_DIR/$package.success"
  NUM_SUCCESS=$((NUM_SUCCESS + 1))
done < packages.txt

echo "*** Done, num success=$NUM_SUCCESS"
