from pathlib import Path

from python.log import log
from utils import PROJECT_PATH, mk_empty_dir
import docker
import tarfile

GET_DATA_PATH = PROJECT_PATH / "get-data"


def download(outdir: Path, langs: str, count: int, force: bool):
    log.warning(f"currently langs are unused: {langs}")

    mk_empty_dir(outdir, force)
    out_tar = outdir / "data.tar.gz"

    client = docker.from_env()
    image = client.images.build(path=str(GET_DATA_PATH), tag="get-data", buildargs={"N": count})[0]
    container = client.containers.create(image)

    bits, stat = container.get_archive("/sources")
    with out_tar.open("wb") as f:
        for chunk in bits:
            f.write(chunk)
    container.remove()

    tar = tarfile.open(out_tar, "r:gz")
    tar.extractall()
    tar.close()

    out_tar.unlink()
