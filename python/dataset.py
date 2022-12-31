import pickle
from itertools import count
from pathlib import Path
from time import time
from typing import BinaryIO, Dict

from code_type import CodeType, ExampleDb
from log import log, logging_progress_bar, WithLoggingPbar, Pbar
from model import tokenize
from tokenizers import Tokenizer

import torch

from utils import walk_files


class _ModelDataRepoPbars:
    def __init__(
            self,
            examples: Pbar,
            artifacts: Pbar,
            source_files: Pbar,
            disassembled_files: Pbar):
        self.examples = examples
        self.artifacts = artifacts
        self.source_files = source_files
        self.disassembled_files = disassembled_files


class _WithModelDataRepoPbars:
    def __init__(self, num_artifacts: int, num_source_files: int, num_disassembled_files: int, max_len: int):
        # descriptions have trailing spaces to align the progress bars
        self.positions = count()
        self.examples = self._pbar("source-examples", max_len)
        self.artifacts = self._pbar("artifacts", num_artifacts)
        self.source_files = self._pbar("source-files", num_source_files)
        self.disassembled_files = self._pbar("disassembled-files", num_disassembled_files)

    MAX_DESC_LEN = 18

    def _pbar(self, desc: str, total: int) -> WithLoggingPbar:
        return logging_progress_bar(
            desc=desc.ljust(self.MAX_DESC_LEN),
            total=total,
            position=next(self.positions),
            leave=False
        )

    def __enter__(self) -> _ModelDataRepoPbars:
        return _ModelDataRepoPbars(
            examples=self.examples.__enter__(),
            artifacts=self.artifacts.__enter__(),
            source_files=self.source_files.__enter__(),
            disassembled_files=self.disassembled_files.__enter__()
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.examples.__exit__(exc_type, exc_val, exc_tb)
        self.artifacts.__exit__(exc_type, exc_val, exc_tb)
        self.source_files.__exit__(exc_type, exc_val, exc_tb)
        self.disassembled_files.__exit__(exc_type, exc_val, exc_tb)


class ModelData:
    def add_repo(self, code_types: list[CodeType], repo_dir: Path):
        """
        adds an repo (directory of artifacts;
        each artifact is a self-contained directory of source and disassembled files)
        """
        if not repo_dir.exists():
            raise ValueError(f"repo dir {str(repo_dir)} does not exist")

        # noinspection PyShadowingNames
        def get_artifact(file: Path):
            # artifact = <child of root dir which is ancestor of file>
            artifact = file
            while artifact.parent != repo_dir:
                artifact = artifact.parent
            return artifact

        log.info(f"** calculating size of repo {str(repo_dir)}")
        artifacts = set()
        num_source_files = 0
        num_disassembled_files = 0
        for file in walk_files(repo_dir):
            artifact = get_artifact(file)

            for code_type in code_types:
                if any(file.name.endswith(extension) for extension in code_type.disassembled_extensions):
                    num_disassembled_files += 1
                    artifacts.add(artifact)
                elif any(file.name.endswith(extension) for extension in code_type.source_extensions):
                    num_source_files += 1
                    artifacts.add(artifact)

        log.info(f"** adding repo {str(repo_dir)}")
        original_num_examples = len(self)
        start_time = time()
        try:
            with _WithModelDataRepoPbars(len(artifacts), num_source_files, num_disassembled_files, self.max_len) \
                    as pbars:
                pbars.examples.update(len(self))
                for artifact_dir in sorted(artifacts):
                    num_new_examples = self._add_artifact(code_types, artifact_dir, pbars)
                    pbars.artifacts.update(1)
                    pbars.examples.update(num_new_examples)
                    if 0 < self.max_len < len(self):
                        log.info("** max_len reached, not adding any more examples")
                        break
        except KeyboardInterrupt:
            log.info(f"** interrupted, not adding any more examples for repo {str(repo_dir)}")
            raise KeyboardInterrupt
        except Exception as e:
            log.exception(f"** error while adding repo {str(repo_dir)}")
            raise e
        finally:
            num_new_examples = len(self) - original_num_examples
            duration = time() - start_time
            log.info(f"** added {num_new_examples} examples from repo {str(repo_dir)} ({'%.2f' % duration} seconds)")

    def _add_artifact(self, code_types: list[CodeType], artifact_dir: Path, pbars: _ModelDataRepoPbars) -> int:
        """
        adds an artifact (self-contained directory of source and disassembled files).
        This is private because of pbar: we could create a public version which creates a pbar for one artifact
        and call this within the with _WithModelDataArtifactPbars as pbars clause (then make pbars type a Union)
        """
        if not artifact_dir.exists():
            raise ValueError(f"artifact dir {str(artifact_dir)} does not exist")

        dbs: Dict[CodeType, ExampleDb] = {code_type: code_type.ExampleDb() for code_type in code_types}
        num_processed_source_examples = 0
        num_processed_disassembled_examples = 0

        log.info(f"* adding artifact {artifact_dir.name}")
        start_time = time()
        try:
            for file in walk_files(artifact_dir):
                for code_type in code_types:
                    if not (0 < self.max_len <= num_processed_source_examples) and \
                            any(file.name.endswith(e) for e in code_type.source_extensions) and \
                            not any(file.name.endswith(e) for e in code_type.disassembled_extensions):
                        new_source_examples = dbs[code_type].add_source(file)
                        num_processed_source_examples += new_source_examples
                        pbars.source_files.update(1)
                    if not (0 < self.max_len <= num_processed_disassembled_examples) and \
                            any(file.name.endswith(e) for e in code_type.disassembled_extensions):
                        new_disassembled_examples = dbs[code_type].add_disassembled(file)
                        num_processed_disassembled_examples += new_disassembled_examples
                        pbars.disassembled_files.update(1)
        except KeyboardInterrupt:
            log.info(f"* interrupted, not adding any more examples for artifact {artifact_dir.name}")
            for db in dbs.values():
                db.process_interrupt()
            raise KeyboardInterrupt
        except Exception as e:
            log.exception(f"* error while adding artifact {artifact_dir.name}")
            for db in dbs.values():
                db.process_interrupt()
            raise e
        finally:
            total_num_examples_added = 0
            num_examples_added_for_code_type = {}
            for code_type, db in dbs.items():
                num_examples_added = 0
                for source, disassembled in db.build_examples():
                    self.source_disassembled_code_types.append(code_type)
                    self.sources.append(source)
                    self.disassembleds.append(disassembled)
                    num_examples_added += 1
                total_num_examples_added += num_examples_added
                num_examples_added_for_code_type[code_type] = num_examples_added
            num_examples_added_for_code_type_str = ", ".join(
                f"{str(code_type)}: {num_examples_added}"
                for code_type, num_examples_added in num_examples_added_for_code_type.items()
            )
            duration = time() - start_time
            log.info(f"* added {total_num_examples_added} [{num_examples_added_for_code_type_str}] examples from "
                     f"artifact {artifact_dir.name} ({'%.2f' % duration} seconds)")
            return total_num_examples_added

    def split_off_end(self, interval: float):
        split_index = int(len(self) * interval)
        rhs = ModelData()
        rhs.source_disassembled_code_types = self.source_disassembled_code_types[split_index:]
        rhs.sources = self.sources[split_index:]
        rhs.disassembleds = self.disassembleds[split_index:]
        self.source_disassembled_code_types = self.source_disassembled_code_types[:split_index]
        self.sources = self.sources[:split_index]
        self.disassembleds = self.disassembleds[:split_index]
        return rhs

    def limit_code_types(self, code_types: list[CodeType]):
        i = 0
        while i < len(self):
            if self.source_disassembled_code_types[i] not in code_types:
                self.source_disassembled_code_types.pop(i)
                self.sources.pop(i)
                self.disassembleds.pop(i)
            else:
                i += 1

    # noinspection PyShadowingNames
    def limit_count(self, count: int):
        self.source_disassembled_code_types = self.source_disassembled_code_types[:count]
        self.sources = self.sources[:count]
        self.disassembleds = self.disassembleds[:count]

    def __len__(self):
        return len(self.sources)

    def __init__(self, max_len: int = 0):
        self.max_len = max_len
        self.source_disassembled_code_types = []
        self.sources = []
        self.disassembleds = []

    def postprocess(self):
        if len(self) > 0:
            sources_and_disassembleds_and_code_types = \
                list(zip(self.sources, self.disassembleds, self.source_disassembled_code_types))
            sources_and_disassembleds_and_code_types.sort(key=lambda x: len(x[0]))
            self.sources, self.disassembleds, self.source_disassembled_code_types = \
                [list(s) for s in zip(*sources_and_disassembleds_and_code_types)]

    PICKLE_PROTOCOL = 5

    def save(self, path_or_file: Path | BinaryIO):
        self.postprocess()
        if isinstance(path_or_file, Path):
            with path_or_file.open("wb") as file:
                self.save(file)
        else:
            pickle.dump(self, path_or_file, protocol=self.PICKLE_PROTOCOL)

    @staticmethod
    def load(path: Path):
        with path.open("rb") as file:
            return pickle.load(file)


# (idk why but IntelliJ can't find torch.utils.data)
# noinspection PyUnresolvedReferences
class ModelDataset(torch.utils.data.Dataset):
    def __init__(self, data: ModelData, tokenizer: Tokenizer):
        if len(data) == 0:
            raise ValueError("Cannot create dataset from no data")
        self.encodings = tokenize(tokenizer, data.disassembleds)
        self.labels = tokenize(tokenizer, data.sources)

    def __len__(self):
        return len(self.labels.input_ids)

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels.input_ids[idx])
        return item
