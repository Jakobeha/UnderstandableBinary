#!/bin/bash

PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
INSTALL_DIR=$PARENT_DIR/../../../UnderstandableBinary-data/conan
NUM_PACKAGES=4294967295
RECREATE=0

# Show help if necessary
function show_help() {
  usage="Usage: $0 [-o INSTALL_DIR] [-f]

Download and build packages from the conan-central (JFrog) repository

    -n NUM_PACKAGES  Number of packages to install. Default: all
    -o INSTALL_DIR   Directory where the packages are installed. Default: $INSTALL_DIR
    -f               Recreate the conan root, deleting old files. otherwise we will resume installing. Default: false"
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

echo "*** Using CONAN_USER_HOME=$INSTALL_DIR"
export CONAN_USER_HOME=$INSTALL_DIR

if [ -d "$INSTALL_DIR" ] && [ $RECREATE -eq 1 ]; then
    echo "*** Removing install dir and recreating"
    rm -rf "$INSTALL_DIR"
fi

if [ ! -d "$INSTALL_DIR" ]; then
  mkdir "$INSTALL_DIR" || exit 1
  mkdir "$INSTALL_DIR/stats"
fi

cd "$INSTALL_DIR" || exit 1

echo "*** Searching for packages to install"
# fill packages.txt with the latest version of each package on conancenter, and only up to $NUM_PACKAGES
conan search -r conancenter | tail -n +3 | tail -r | awk -F '/' '!seen[$1]++' | tail -r | head -n "$NUM_PACKAGES" > packages.txt

echo "*** Installing $(< packages.txt wc -l) packages"
NUM_SUCCESS=0
while read -r package; do
  package_name=$(echo "$package" | cut -d '/' -f1)
  if [ -f "stats/$package_name.failed" ]; then
    echo "** Skipping $package_name (failed before, num success=$NUM_SUCCESS)"
    continue
  elif [ -f "stats/$package_name.success" ]; then
    echo "** Skipping $package_name (already done, num success=$NUM_SUCCESS)"
    NUM_SUCCESS=$((NUM_SUCCESS + 1))
    continue
  fi
  echo "** conan install $package (num success=$NUM_SUCCESS)"
  conan install "$package@" -r conancenter -s build_type=Debug --build
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
    echo "** Failed to install $package_name"
    # Write file so that we skip in subsequent calls
    touch "stats/$package_name.failed"
    continue
  fi
  touch "stats/$package_name.success"
  NUM_SUCCESS=$((NUM_SUCCESS + 1))
done < packages.txt

echo "*** Done, num success=$NUM_SUCCESS"
