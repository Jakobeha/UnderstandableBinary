from pathlib import Path
from sys import argv

from code_types import ALL_LANGS
from generate import generate
from train import train
from transform_ir import transform_ir
from transform import transform
from utils import DEFAULT_DATASET_PATH, DEFAULT_MODEL_PATH, INT32_MAX, path_or_float, DEFAULT_EXAMPLES_PATH, run_script


def get_data_cmd(_args):
    # Forward to get-data/run.sh (argv[2:] drops cmdline.py and subprocess argument)
    run_script("get-data/run.sh", argv[2:])


def generate_cmd(args):
    generate(args.i, args.o, args.l, args.n, args.f)


def train_cmd(args):
    train(args.i, args.eval, args.o, args.l, args.n, args.f, args.resume)


def transform_ir_cmd(args):
    transform_ir(args.i, args.o, args.m, args.l, args.n, args.f)


def transform_cmd(args):
    transform(args.i, args.o, args.m, args.l, args.n, args.f)


def main():
    import argparse
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(required=True)

    get_data_parser = subparsers.add_parser(
        "get-data",
        help="download, build, and decompile the sources to get data to generate examples from",
        add_help=False
    )
    get_data_parser.add_argument('-h', action="store_true")
    get_data_parser.add_argument('...', nargs=argparse.REMAINDER)
    get_data_parser.set_defaults(func=get_data_cmd)

    generate_parser = subparsers.add_parser(
        "gen-examples",
        help="scrape .c and .o files and preprocess from an on-disk folder to generate model examples"
    )
    generate_parser.add_argument(
        "-i",
        type=Path,
        help=f"dataset directory (default: {DEFAULT_DATASET_PATH})",
        default=DEFAULT_DATASET_PATH
    )
    generate_parser.add_argument(
        "-o",
        type=Path,
        help=f"output file (default: {DEFAULT_EXAMPLES_PATH})",
        default=DEFAULT_EXAMPLES_PATH
    )
    generate_parser.add_argument(
        "-f",
        help="force overwrite output file",
        action="store_true"
    )
    generate_parser.add_argument(
        "-l",
        type=str,
        help="languages (separated by commas, default = all)",
        default=ALL_LANGS
    )
    generate_parser.add_argument(
        "-n",
        type=int,
        help="number of examples to add (default = all)",
        default=INT32_MAX
    )
    generate_parser.set_defaults(func=generate_cmd)

    train_parser = subparsers.add_parser(
        "train",
        help="train a model from a dataset of input and output IR"
    )
    train_parser.add_argument(
        "-i",
        type=Path,
        help=f"input examples file (default = {DEFAULT_EXAMPLES_PATH})",
        default=DEFAULT_EXAMPLES_PATH
    )
    train_parser.add_argument(
        "--eval",
        type=path_or_float,
        help="if a path, directory to separate evaluation data."
             "Otherwise should be a ratio, and will use that ratio of the input."
             "Default = 0, which means we don't run evaluations",
        default=0
    )
    train_parser.add_argument(
        "-o",
        type=Path,
        help=f"output (model) directory (default = {DEFAULT_MODEL_PATH})",
        default=DEFAULT_MODEL_PATH
    )
    train_parser.add_argument(
        "-f",
        help="force overwrite output directory. Ignored if --resume is passed",
        action="store_true"
    )
    train_parser.add_argument(
        "-l",
        type=str,
        help="languages (separated by commas, default = all)."
             "Note that actual languages used is the intersection of this and the languages in the example",
        default=ALL_LANGS
    )
    train_parser.add_argument(
        "-n",
        type=int,
        help="number of examples to pass to model (default = all)"
             "Note that actual number of examples used is the minimum of this and the number of examples in the file",
        default=INT32_MAX
    )
    train_parser.add_argument(
        "--resume",
        action="store_true",
        help="resume training from the last checkpoint"
    )
    train_parser.set_defaults(func=train_cmd)

    transform_ir_parser = subparsers.add_parser(
        "transform-ir",
        help="transform a directory of input IR into output IR."
             "This runs the raw model, but usually you want transform which converts to/from IR"
    )
    transform_ir_parser.add_argument(
        "-i",
        type=Path,
        help="input directory",
        required=True
    )
    transform_ir_parser.add_argument(
        "-o",
        type=Path,
        help="output directory",
        required=True
    )
    transform_ir_parser.add_argument(
        "-f",
        help="force overwrite of output directory",
        action="store_true"
    )
    transform_ir_parser.add_argument(
        "-m",
        type=Path,
        help="model directory",
        default=DEFAULT_MODEL_PATH
    )
    transform_ir_parser.add_argument(
        "-l",
        type=str,
        help="languages (separated by commas, default = all)",
        default=ALL_LANGS
    )
    transform_ir_parser.add_argument(
        "-n",
        type=int,
        help="number of files to transform (default = all files)",
        default=INT32_MAX
    )
    transform_ir_parser.set_defaults(func=transform_ir_cmd)

    transform_parser = subparsers.add_parser(
        "transform",
        help="transform a directory of assembly into inferred source code"
    )
    transform_parser.add_argument(
        "-i",
        type=Path,
        help="input directory",
        required=True
    )
    transform_parser.add_argument(
        "-o",
        type=Path,
        help="output directory",
        required=True
    )
    transform_parser.add_argument(
        "-f",
        help="force overwrite of output directory",
        action="store_true"
    )
    transform_parser.add_argument(
        "-m",
        type=Path,
        help="model directory",
        default=DEFAULT_MODEL_PATH
    )
    transform_parser.add_argument(
        "-l",
        type=str,
        help="languages (separated by commas, default = all)",
        default=ALL_LANGS
    )
    transform_parser.add_argument(
        "-n",
        type=int,
        help="number of files to transform (default = all files)",
        default=INT32_MAX
    )
    transform_parser.set_defaults(func=transform_cmd)

    func_and_args = parser.parse_args()
    func_and_args.func(func_and_args)


if __name__ == "__main__":
    main()
