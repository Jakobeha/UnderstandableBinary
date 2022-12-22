#!/bin/bash

N="$1"
if [ -z "$N" ]; then
  echo "Usage: $0 <number of packages to install>"
  exit 1
fi

set -o pipefail

echo "*** FETCHING LIST OF $N PACKAGES"
apt-cache search "" | head -"$N" | cut -d' ' -f1 > packages.txt

echo "*** SOURCING AND BUILDING $(< packages.txt wc -l) PACKAGES..."
NUM_SUCCESS=0
mkdir sources
cd sources || exit 1
while read -r package; do
  echo "** build-dep $package (num success=$NUM_SUCCESS)"
  apt-get build-dep -yf --allow-unauthenticated "$package"
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
    echo "** Failed to build-dep $package"
  else
    echo "** source $package (num success=$NUM_SUCCESS)"
    apt-get source -yb --allow-unauthenticated "$package"
  # shellcheck disable=SC2181
    if [ $? -ne 0 ]; then
      echo "** Failed to source $package"
    else
      NUM_SUCCESS=$((NUM_SUCCESS + 1))
    fi
  fi
done < ../packages.txt

echo "*** SOURCED AND BUILT $NUM_SUCCESS PACKAGES..."
