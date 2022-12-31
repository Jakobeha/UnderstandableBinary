# Python scripts

`python/cmdline.py` is the main one, since this is a command-line app

## Directory layout

- `python/cmdline.py`: Command line interface
- Commands:
    - `python/generate.py`
    - `python/train.py`
    - `python/transform_ir.py` (currently unused)
    - `python/transform.py`
- Model helpers 
  - `python/model.py`: General ML functions used in `train.py` and `transform*.py`
  - `python/dataset.py`: Dataset classes used mainly in `train.py`
- `python/transform_gen.py`: Transform each file in a directory using a model; abstract logic used by `transform_ir.py` and `transform.py`
- `python/log.py`: Logging
- `python/utils.py`: Utility functions and constants

# Requirements

For `generate`:

- Headers. Xcode Command Line tools if on macOS. May also want to install additional headers.
  Ultimately the more global headers, the more source files can be parsed
- `clang`

For `train` and `transform`:

- Select the right `torch` dependency in `pyproject.toml` (unfortunately this is not yet automated)
- Note that these will take a while (not as much needed for `transform`)