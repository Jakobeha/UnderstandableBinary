from pathlib import Path
from download import download
from compile import compile


def download_cmd(args):
    download(args.i, args.o, args.t, args.n, args.f)


def preprocess_compile_cmd(args):
    compile(args.i, args.o, args.t, args.n, args.f)


def preprocess_in_ir_cmd(args):
    pass  # TODO


def preprocess_out_ir_cmd(args):
    pass  # TODO


def preprocess_out_src_cmd(args):
    pass  # TODO


def split_cmd(args):
    pass  # TODO


def train_ir_cmd(args):
    pass  # TODO


def transform_ir_cmd(args):
    pass  # TODO


def train_cmd(args):
    pass  # TODO


def transform_cmd(args):
    pass  # TODO


def main():
    import argparse
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(required=True)

    granular_parser = subparsers.add_parser(
        "granular",
        help="granular commands, sequences of these are run by the other commands"
    )

    granular_subparsers = granular_parser.add_subparsers(required=True)

    download_parser = granular_subparsers.add_parser(
        "download",
        help="download data from a package repository (default: Debian stable)"
    )
    download_parser.add_argument(
        "-i",
        type=str,
        help="input package repository, format must be same as //sources.debian.org/api/... (which is the default)",
        default="https://sources.debian.org/api/..."
    )
    download_parser.add_argument(
        "-o",
        type=Path,
        help="output directory",
        required=True
    )
    download_parser.add_argument(
        "-f",
        help="force overwrite of output directory",
        action="store_true"
    )
    download_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        required=True
    )
    download_parser.add_argument(
        "-n",
        type=int,
        help="number of files to add (default = 0 = all files, but note that the full dataset is over 1TB)",
        default=0
    )
    download_parser.set_defaults(func=download_cmd)

    preprocess_parser = granular_subparsers.add_parser(
        "preprocess",
        help="add data to a dataset before training or transforming"
    )
    preprocess_parser.add_argument(
        "-i",
        type=Path,
        help="input directory",
        required=True
    )
    preprocess_parser.add_argument(
        "-o",
        type=Path,
        help="output directory (defaults to input)",
        default=None
    )
    preprocess_parser.add_argument(
        "-f",
        help="force overwrite of data in output directory",
        action="store_true"
    )
    preprocess_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        required=True
    )
    preprocess_parser.add_argument(
        "-n",
        type=int,
        help="number of files to add (default = 0 = all files)",
        default=0
    )

    preprocess_subparsers = preprocess_parser.add_subparsers(required=True)
    preprocess_subparsers.add_parser(
        "compile",
        help="compile the code into assembly"
    ).set_defaults(func=preprocess_compile_cmd)
    preprocess_subparsers.add_parser(
        "in-ir",
        help="translate the assembly into model input IR",
    ).set_defaults(func=preprocess_in_ir_cmd)
    preprocess_subparsers.add_parser(
        "out-ir",
        help="translate the source into model output IR",
    ).set_defaults(func=preprocess_out_ir_cmd)
    preprocess_subparsers.add_parser(
        "out-src",
        help="translate model output IR into source"
    ).set_defaults(func=preprocess_out_src_cmd)

    split_parser = granular_subparsers.add_parser(
        "split",
        help="split dataset into training, test, and eval sets"
    )
    split_parser.add_argument(
        "-i",
        type=Path,
        help="input directory",
        required=True
    )
    split_parser.add_argument(
        "-o",
        type=Path,
        help="output directory",
        required=True
    )
    split_parser.add_argument(
        "-f",
        help="force overwrite of output directory",
        action="store_true"
    )
    split_parser.add_argument(
        "-n",
        type=int,
        help="number of files to take from the original dataset (default = 0 = all files)",
        default=0
    )
    split_parser.add_argument(
        "--test-ratio",
        type=float,
        help="ratio of test data",
        default=0.2
    )
    split_parser.add_argument(
        "--eval-ratio",
        type=float,
        help="ratio of eval data",
        default=0.2
    )
    split_parser.set_defaults(func=split_cmd)

    train_ir_parser = granular_subparsers.add_parser(
        "train-ir",
        help="train a model from a dataset of input and output IR"
    )
    train_ir_parser.add_argument(
        "-i",
        type=Path,
        help="input (IR dataset) directory; should have \"train\", \"test\", and \"eval\" subdirectories",
        required=True
    )
    train_ir_parser.add_argument(
        "-o",
        type=Path,
        help="output (model) directory (defaults to \"{input directory}/model\")",
        default=None
    )
    train_ir_parser.add_argument(
        "-f",
        help="force overwrite of output directory",
        action="store_true"
    )
    train_ir_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        required=True
    )
    train_ir_parser.add_argument(
        "--skip-evaluations",
        action="store_true",
        help="skip evaluations"
    )
    train_ir_parser.add_argument(
        "--resume",
        action="store_false",
        default=True,
        help="resume training from the last checkpoint"
    )
    train_ir_parser.set_defaults(func=train_ir_cmd)

    transform_ir_parser = granular_subparsers.add_parser(
        "transform-ir",
        help="transform a directory of input IR into output IR"
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
        required=True
    )
    transform_ir_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        required=True
    )
    transform_ir_parser.set_defaults(func=transform_ir_cmd)

    train_parser = subparsers.add_parser(
        "train",
        help="download and train a model using data from a package repository (default: Debian Stable)"
    )
    train_parser.add_argument(
        "-i",
        type=str,
        help="input package repository, format must be same as //sources.debian.org/api/... (which is the default)",
        default="https://sources.debian.org/api/..."
    )
    train_parser.add_argument(
        "-o",
        type=Path,
        help="output (model) directory",
        required=True
    )
    train_parser.add_argument(
        "-f",
        help="force overwrite of output directory",
        action="store_true"
    )
    train_parser.add_argument(
        "-t",
        type=str,
        help="code type",
        required=True
    )
    train_parser.add_argument(
        "-n",
        type=int,
        help="number of files to add (default = 0 = all files, but note that the full dataset is over 1TB)",
        default=0
    )
    train_parser.add_argument(
        "--skip-evaluations",
        action="store_true",
        help="skip evaluations"
    )
    train_parser.add_argument(
        "--resume",
        action="store_false",
        default=True,
        help="resume training from the last checkpoint"
    )
    train_parser.set_defaults(func=train_cmd)

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
        required=True
    )
    transform_parser.add_argument(
        "-t",
        type=str,
        help="code type (default is inferred from file extension)",
        default=None
    )
    transform_parser.add_argument(
        "-n",
        type=int,
        help="number of files to transform (default = 0 = all files)",
        default=0
    )
    transform_parser.set_defaults(func=transform_cmd)

    func_and_args = parser.parse_args()
    func_and_args.func(func_and_args)


if __name__ == "__main__":
    main()
