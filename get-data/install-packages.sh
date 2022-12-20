#!/bin/bash

N="$1"
if [ -z "$N" ]; then
  echo "Usage: $0 <number of packages to install>"
  exit 1
fi


apt-get install dpkg-dev -y --allow-unauthenticated

echo "*** FETCHING PACKAGE LIST ($N PACKAGES)"
apt-cache search "" | head -"$N" > packages.txt

echo "*** INSTALLING PACKAGES"
recurse () {
  # Even though we do apt-get build-deps -y, we still need yes command because some packages (apt-get-ng, jack2, etc) ask for extra confirmations and will block otherwise
  # shellcheck disable=SC2046
  if yes | apt-get build-dep -yf --allow-unauthenticated $(cat packages.txt | cut -d' ' -f1 | tr '\n' ' ') 2>errors.txt | tee log.txt ; then
      echo "*** INSTALLED PACKAGES"
  elif grep -q "The following packages have unmet dependencies:" log.txt ; then
      echo "*** REMOVING CONFLICTING PACKAGES..."
      # Get the packages causing conflicts
      cat log.txt | sed "s/.*The following packages have unmet dependencies://" | sed 's/^[ \t]*//;s/[ \t]*$//' | cut -d' ' -f1 | sort | uniq > log.txt
      # Remove them from the list of packages to install
      grep -vxf log.txt packages.txt > packages2.txt; mv packages2.txt packages.txt
      rm log.txt
      rm errors.txt
      # Retry
      recurse
  else
      echo "*** FAILED TO INSTALL PACKAGES"
      cat errors.txt
      exit 1
  fi
}
recurse

echo "DOWNLOADING PACKAGE SOURCES..."
mkdir sources
cd sources || exit 1
# shellcheck disable=SC2046
apt-get source -yb --allow-unauthenticated $(cat ../packages.txt | cut -d' ' -f1 | tr '\n' ' ')

# apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

echo "INSTALLED PACKAGES..."
