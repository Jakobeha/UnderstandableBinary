import gc
from pathlib import Path

import evaluate
import numpy as np
import torch
from transformers import TrainingArguments, Trainer

from code_types import CODE_TYPES
from dataset import ModelData, ModelDataset
from model import get_model, get_tokenizer
from utils import check_dir, mk_empty_dir


def train(
        dataset_dir: Path,
        eval_path_or_ratio: Path | float,
        model_dir: Path,
        lang: str,
        count: int,
        force: bool,
        resume: bool,
        use_cached_model_data: bool):
    check_dir(dataset_dir)
    if resume:
        model_dir.mkdir(parents=True, exist_ok=True)
    else:
        mk_empty_dir(model_dir, force)

    tokenizer = get_tokenizer()
    model = get_model(model_dir)
    cached_model_data_path = model_dir / "cached_model.dat"
    train_dataset, eval_dataset = get_datasets(
        tokenizer,
        dataset_dir,
        use_cached_model_data,
        cached_model_data_path,
        eval_path_or_ratio,
        lang,
        count
    )
    do_eval = eval_dataset is not None
    metric = evaluate.load("accuracy") if do_eval else None

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits[0], axis=-1)
        return np.average(np.vectorize(metric.compute)(predictions=predictions, references=labels))

    training_args = TrainingArguments(
        output_dir=str(model_dir),
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1 if do_eval else None,
        evaluation_strategy="epoch" if do_eval else "no",
        do_eval=do_eval
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics if do_eval else None,
    )

    gc.collect()
    torch.cuda.empty_cache()

    trainer.train()


def get_datasets(
        tokenizer,
        dataset_dir: Path,
        use_cached_model_data: bool,
        cached_model_data_path: Path,
        eval_path_or_ratio: Path | float,
        langs: str,
        count: int) -> tuple[ModelDataset, ModelDataset | None]:
    code_types = [CODE_TYPES[lang] for lang in langs.split(",")]
    if use_cached_model_data and cached_model_data_path.exists():
        train_data = ModelData.load(cached_model_data_path)
        assert train_data.code_types == code_types, "Cached model data has different code types"
    else:
        train_data = ModelData(code_types, count)
        train_data.add_dir(dataset_dir)
        train_data.save(cached_model_data_path)
    eval_data: ModelData | None
    if isinstance(eval_path_or_ratio, Path):
        eval_data = ModelData(code_types, count)
        eval_data.add_dir(eval_path_or_ratio)
    elif eval_path_or_ratio != 0:
        eval_data = train_data.split_off_end(eval_path_or_ratio)
    else:
        eval_data = None
    train_dataset = ModelDataset(train_data, tokenizer)
    eval_dataset = ModelDataset(eval_data, tokenizer) if eval_data else None
    return train_dataset, eval_dataset
