# UnderstandableBinary - ML binary demangler

## What is this?

This is a project to use machine learning to convert raw decompiled binary files into cleaner variations.

We take a large dataset of C/C++ code, compile it, decompile the binaries, then train a model to translate the decompiled binaries into their original version,.

Afterward, we have a model which can convert ugly decompiled code into cleaner code.

## How to install

Install dependencies using your platform's package manager (recommend [Homebrew](https://brew.sh/) on macOS):

- [Git LFS](https://git-lfs.com/)
- [clang 14.0.6](https://releases.llvm.org/download.html)
- [vcpkg](https://vcpkg.io/en/index.html)

```shell
> git clone git@github.com:Jakobeha/UnderstandableBinary.git
```

## How to use

```shell
> cd UnderstandableBinary
> run.sh [options]...
```

You can also open in IntelliJ and there are sample run configurations.
Note that you may need to change some global library locations (e.g. path to Poetry)

## Project layout

This project uses many different languages and frameworks. READMEs and `run.sh` scripts are in subdirectories.
The root is an IntelliJ project, however modules are in subdirectories.

- `../UnderstandableBinary-data/`: The default location where the dataset is generated and stored.
  This cannot be in `UnderstandableBinary/` because the dataset is extremely large and contains code,
  which confuses a lot of tools and find and makes everything a hassle.
  You can override the dataset dir, and you may want to make it on a separate volume with more storage.
- `python/`: Python scripts which use [poetry](https://python-poetry.org/) for dependency management.
  Mainly for training and running the model since that is in Python
- `get-data/`: Generate dataset
  - `apt/`: Download and build code from debian APT repo
  - `vcpkg/`: Download and build code from [vcpkg](https://vcpkg.io/en/index.html) repo
  - `decompile/`: decompile binaries using [Ghidra](https://ghidra-sre.org/)
- `local/`: Local directory where you can store scratch data which isn't the dataset. Also, some log files are stored here
  - `ghidra_logs/`: Ghidra script log files 
- `docs/`: documentation

## Related

- [N-Bref](https://github.com/facebookresearch/nbref): A neural-based decompiler framework and binary analysis tool
- [G-3PO](https://medium.com/tenable-techblog/g-3po-a-protocol-droid-for-ghidra-4b46fa72f1ff) and [GptHidra](https://github.com/evyatar9/GptHidra): generate an explanation for a decompiled function and suggest variable names (uses GPT3 and Ghidra)
- [Gepetto](https://github.com/JusticeRage/Gepetto): generate a doc-comment for a decompiled function, plus rename variables and add comments in the function body (uses GPT3 and IDA Pro)

## Contributing

Conventions:

- File and directory names are usually `kebab-case` unless there's another reason (e.g. Java)
- Use PEP and shellcheck (IntelliJ defaults)

TODO: add more