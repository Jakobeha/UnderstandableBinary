# get-data/apt

Build packages from an open-source repository (Debian APT) to get code for training an ML model.

## Files

`run.sh [-n NUM_PACKAGES] [-o INSTALL_DIR]` to download and build the packages into INSTALL_DIR

- `Dockerfile`: Generates a docker image to build packages (doesn't build packages, because if the build fails we can't restart, but has `source-packages.sh` which is the script to do so)
- `source-packages.sh`: Installs dependencies of, downloads source, and builds the first `n` packages. Run while generating the docker image
- `deb-sources.list`: Repositories to get debian packages and package sources
