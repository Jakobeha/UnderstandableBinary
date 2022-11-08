# UnderstandableBinary - use ML to analyze and disassemble binary files

## What is this?

This is a project to use machine learning to analyze and disassemble binary files. It is a work in progress. TODO

## How to use

`./run.sh`

## Project layout

The root project is a python package which uses [poetry](https://python-poetry.org/) for dependency management, however there may be sub-packages in Rust or other languages. The python scripts are mainly wrappers which handle simple tasks, the sub-packages and HuggingFace libraries do the heavy lifting

- `python/*`: Python scripts
  - `python/cmdline.py`: Command line interface
  - `python/data.py`: Dataset functions
  - `python/log.py`: Logging
- `local/`: Local directory you can store downloaded / trained models which is not committed

TODO: add more