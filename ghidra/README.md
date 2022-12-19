# UnderstandableBinary ghidra distribution and scripts

How to use:
- Unzip `latest_release.tar.gz` (TODO automate this when necessary, we compress to reduce Git file count and size)
- Run the shell script `disassemble [<folder with object files>] [<timeout>] [<process existing>]`

More info:

- The Java files are Ghidra scripts, `latest_release` is a Ghidra release.
- The shell script runs Ghidra in headless mode (no GUI), but you can also open Ghidra and run the scripts from there
- `BatchDecompile.java` takes a directory of `.o` files and analyzes / decompiles them all, writing `.o.c` files.
- Ghidra has a lot of options. The script just does auto-import and auto-analyze with default options

How to develop:

- Open in IntelliJ
- If you are getting unresolved import errors, download and install [intellij-ghidra](https://github.com/garyttierney/intellij-ghidra) and add Ghidra facets as specified in the plugin's README (note: version on IntelliJ marketplace does not work, you must install the Git release)