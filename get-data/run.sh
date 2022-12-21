PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DATASET_DIR=$PARENT_DIR/../local/dataset

N="$1"
if [ -z "$N" ]; then
  echo "Usage: $0 <number of packages to install> [<dataset dir>]"
  exit 1
fi

if [ -n "$2" ]; then
  DATASET_DIR="$2"
fi

docker build -t get-data "$PARENT_DIR"
docker run --name get-data get-data bash /install-packages.sh "$N"
docker stop get-data
docker cp get-data:/sources/. "$DATASET_DIR"