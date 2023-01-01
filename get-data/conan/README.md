# get-data/vcpkg

Download and build all packages from [conan](https://conan.io)

## Dependencies

- [conan](https://conan.io) (you must have them installed, however we set CONAN_USER_HOME to a fake home so it should
  not modify your actual cache)

## Files

`run.sh [-n NUM_PACKAGES] [-o INSTALL_DIR]` to download and build the packages into INSTALL_DIR

