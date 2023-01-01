# get-data/decompile

decompile the code in the dataset we've already generated using Ghidra and a Ghidra script.

## Setup requirements

- Linux: nothing
- macOS: nothing, but you must allow some unsigned code and rerun due to SIP (see [https://support.apple.com/en-us/HT202491](https://support.apple.com/en-us/HT202491) section "If you want to open an app that hasn’t been notarized or is from an unidentified developer")
- Windows: untested and my not work

## Files

`run.sh [-o DATASET_DIR] [-l SCRIPT_LOG_DIR] [-j NUM_INSTANCES] [-f] [-F]` to decompile files in DATASET_DIR (output files are in the same directory as the inputs)

More info:

- `ghidra` is a Ghidra release.
- `BatchDecompile.java` is a Ghidra script. takes a directory of `.o` files and analyzes / decompiles them all, writing `.o.c` files.
- The shell script runs Ghidra in headless mode (no GUI), but you can also open Ghidra and run the scripts from there
- Ghidra has a lot of options. The script just does auto-import and auto-analyze with default options

## How to develop

- Open in IntelliJ
- If you are getting unresolved import errors, download and install [intellij-ghidra](https://github.com/garyttierney/intellij-ghidra) and add Ghidra facets as specified in the plugin's README (note: version on IntelliJ marketplace does not work, you must install the Git release)
- You should get code completion for Ghidra classes in the script
