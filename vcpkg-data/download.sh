#!/bin/bash

export VCPKG_ROOT=vcpkg
if [ ! -d $VCPKG_ROOT ]; then
  git clone https://github.com/microsoft/vcpkg "$VCPKG_ROOT"
  mkdir "$VCPKG_ROOT/failures"
fi

vcpkg search | cut -d ' ' -f1 | ghead -n -2 > packages.txt

echo "*** Installing $(< packages.txt wc -l) packages"

NUM_SUCCESS=0
while read -r package; do
  if compgen -G "$VCPKG_ROOT/failures/$package.*.failed*" > /dev/null; then
    echo "** Skipping $package (failed before, num success=$NUM_SUCCESS)"
    continue
  fi
  if compgen -G "$VCPKG_ROOT/packages/$package*" > /dev/null; then
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
    touch "$VCPKG_ROOT/failures/$package.install.failed"
    continue
  fi
  NUM_SUCCESS=$((NUM_SUCCESS + 1))
done < packages.txt
