PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DATASET_DIR=$PARENT_DIR/../local/dataset

N="$1"
if [ -z "$N" ]; then
  echo "Usage: $0 <number of packages to install>"
  exit 1
fi

docker build -t get-data "$PARENT_DIR" --build-arg N="$1"
docker create --name get-data get-data
docker cp get-data:/sources "$DATASET_DIR"