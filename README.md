# UnderstandableBinary - use ML to analyze and disassemble binary files

## What is this?

This is a project to use machine learning to analyze and disassemble binary files. It is a work in progress. TODO

## How to install

Install [Git LFS](https://git-lfs.com/) if not already, then `git clone ...`

## How to use

`./run.sh`

## Project layout

The root project is a python package which uses [poetry](https://python-poetry.org/) for dependency management, however there may be sub-packages in Rust or other languages. The python scripts are mainly wrappers which handle simple tasks, the sub-packages and HuggingFace libraries do the heavy lifting

- `python/*`: Python scripts
- `get-data`: Dockerfile / generator which downloads APT repositories and runs the preprocessor to generate training examples
- `preprocessor`: Rust project which converts source code and assembly into input and output IR 
  - Dissassembles the object files and divides the source and object into smaller sections which are the examples; converts the assembly into input IR and source into output IR
- `local/`: Local directory where you can store downloaded / trained models which is not committed

TODO: add more