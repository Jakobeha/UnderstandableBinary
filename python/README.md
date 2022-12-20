# Python scripts

`python/cmdline.py` is the main one, since this is a command-line app

## Directory layout

- `python/cmdline.py`: Command line interface
- Commands:
    - `python/download.py`
    - `python/generate.py`
    - `python/train.py`
    - `python/transform_ir.py`
    - `python/transform.py`
- Model helpers 
  - `python/model.py`: General ML functions used in `train.py` and `transform*.py`
  - `python/dataset.py`: Dataset classes used mainly in `train.py`
- `python/transform_gen.py`: Transform each file in a directory using a model; abstract logic used by `transform_ir.py` and `transform.py`
- `python/log.py`: Logging
- `python/utils.py`: Utility functions and constants