# get-data

Create the code dataset by downloading, building, and disassembling

## FILES

`run.sh [-o DATASET_DIR] [-n NUM_FILES] [-p NUM_GHIDRA_INSTANCES] [-f]`: create the dataset

- `apt`: Download and build from debian APT
- `vcpkg`: Download and build from [vcpkg](https://vcpkg.io)
- `ghidra`: Disassemble using [ghidra](https://ghidra-sre.org)
