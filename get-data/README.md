# get-data

Get source and compiled assembly data from an open-source repository (Debian), then runs `../preprocessor` to convert to input/output IR to ultimately generate UnderstandableBinary training examples

## Files

`run.sh <number of packages>` to generate the training examples, all other files are implementation

- `Dockerfile`: Generates a docker image where we can copy out `/data`, which is source/object pairs to pass to `../preprocessor`
- `deb-sources.list`: Repositories to get debian packages and package sources
- `install-packages.sh`: Installs dependencies of, downloads source, and builds the first `n` packages. Run while generating the docker image