from log import logging_progress
import shutil
import os
from pathlib import Path
from datasets import load_dataset
from utils import mk_empty_dir
import itertools

def download(outdir: Path, lang: str, count: int, force: bool):
    mk_empty_dir(outdir, force)
    try:
        access_token = os.getenv("HUGGINGFACE_TOKEN")
        if access_token is None:
            raise Exception(
                "Must set HUGGINGFACE_TOKEN env variable to a huggingface access token which can access \"The Stack\" "
                "dataset"
            )
        dataset_iter = iter(load_dataset(
            "bigcode/the-stack",
            use_auth_token=access_token,
            data_dir=f"data/{lang}",
            split="train",
            streaming=True
        ))
        if count != 0:
            dataset_iter = itertools.islice(dataset_iter, count)
        for entry in logging_progress(
                f"Downloading examples from {lang} dataset",
                dataset_iter,
                total=count if count != 0 else None):
            path = outdir / entry["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(outdir / path, "w") as file:
                file.write(entry["content"])
    except Exception as e:
        shutil.rmtree(outdir)
        raise e