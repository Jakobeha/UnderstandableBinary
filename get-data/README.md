# get-data

Build `N` packages from an open-source repository (Debian) to get code for training an ML model.

## Files

`run.sh <number of packages> [<install dir>]` to build the packages and get the code

- `Dockerfile`: Generates a docker image to build packages (doesn't build packages, because if the build fails we can't restart, but has `source-packages.sh` which is the script to do so)
- `source-packages.sh`: Installs dependencies of, downloads source, and builds the first `n` packages. Run while generating the docker image
- `deb-sources.list`: Repositories to get debian packages and package sources
