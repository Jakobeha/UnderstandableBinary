# get-data

Get source and compiled assembly data from an open-source repository (Debian), then converts to input/output IR to ultimately generate UnderstandableBinary training examples

## Files

`run.sh` to generate the training examples, all other files are implementation

- `Dockerfile`: Generates a docker image where we can copy out `/data`, which is source/object pairs to pass to `preprocessor`
- `deb-sources.list`: Repositories to get debian packages and package sources
- `install-packages.sh`: Installs dependencies of, downloads source, and builds the first `n` packages. Run while generating the docker image
- `scraper`: Gets source/object pairs from a directory of build source (`apt-get source -b`) packages. ~~Run inside of the Docker container~~ Ignored for now, but can be used to quickly get the # of sources without preprocessing
- `preprocessor`: dissassembles the object files and divides the source and object into smaller training examples; converts the assembly into input IR and source into output IR. ~~Run outside of the Docker container for speed~~ Run inside of the docker container (can run outside if performance is affected)