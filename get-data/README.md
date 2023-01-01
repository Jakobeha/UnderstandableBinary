# get-data

Create the code dataset by downloading, building, and disassembling

## FILES

`run.sh [-o DATASET_DIR] [-n NUM_FILES] [-p NUM_GHIDRA_INSTANCES] [-f]`: create the dataset

- `apt`: Download and build from [debian APT](https://wiki.debian.org/Apt)
- `vcpkg`: Download and build from [vcpkg](https://vcpkg.io)
- `conan`: Download and build from [conan](https://conan.io)
- `ghidra`: Disassemble object code in the above using [ghidra](https://ghidra-sre.org)
