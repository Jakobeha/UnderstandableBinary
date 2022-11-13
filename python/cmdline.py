from pathlib import Path
from download import download
from generate import generate
from train import train
from transform_ir import transform_ir
from transform import transform
from python.utils import PROJECT_PATH, INT32_MAX, path_or_float


def download_cmd(args):
    download(args.o, args.t, args.n, args.f)


def generate_cmd(args):
    generate(args.i, args.o, args.t, args.n, args.f)


def train_cmd(args):
    train(args.i, args.eval, args.o, args.t, args.n, args.f, args.resume)


def transform_ir_cmd(args):
    transform_ir(args.i, args.o, args.m, args.t, args.n, args.f)


def transform_cmd(args):
    transform(args.i, args.o, args.m, args.t, args.n, args.f)


def main():
    import argparse
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(required=True)

    download_parser = subparsers.add_parser(
        "download-dataset",
        help="download packages from APT, compile, scrape .c and .o files, and preprocess to generate model examples"
    )
    download_parser.add_argument(
        "-o",
        type=Path,
        help="output directory",
        default=PROJECT_PATH / "local/dataset"
    )
    download_parser.add_argument(
        "-f",
        help="force overwrite output directory",
        action="store_true"
    )
    download_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        default="c"
    )
    download_parser.add_argument(
        "-n",
        type=int,
        help="number of files to add (default = all files, but note that the APT repo is massive and this would take"
             "days if not weeks or months)",
        default=INT32_MAX
    )
    download_parser.set_defaults(func=download_cmd)

    generate_parser = subparsers.add_parser(
        "gen-dataset",
        help="scrape .c and .o files and preprocess from an on-disk folder to generate model examples"
    )
    generate_parser.add_argument(
        "-i",
        type=Path,
        help="input directory (must contain .c and .o files, can contain others and files may be deeply nested)",
        required=True
    )
    generate_parser.add_argument(
        "-o",
        type=Path,
        help="output directory",
        default=PROJECT_PATH / "local/dataset"
    )
    generate_parser.add_argument(
        "-f",
        help="force overwrite output directory",
        action="store_true"
    )
    generate_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        default="c"
    )
    generate_parser.add_argument(
        "-n",
        type=int,
        help="number of files to add (default = all files) (TODO: currently ignored)",
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
        help="input directory, contains the training data",
        default=PROJECT_PATH / "local/dataset"
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
        help="output (model) directory",
        default=PROJECT_PATH / "local/model"
    )
    train_parser.add_argument(
        "-f",
        help="force overwrite output directory. Ignored if --resume is passed",
        action="store_true"
    )
    train_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        default="c"
    )
    train_parser.add_argument(
        "-n",
        type=int,
        help="number of files to pass to model (default = all files)",
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
        default=PROJECT_PATH / "local/model"
    )
    transform_ir_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        default="c"
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
        default=PROJECT_PATH / "local/model"
    )
    transform_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        default="c"
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
