PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DATASET_DIR=$PARENT_DIR/../local/dataset

N="$1"
if [ -z "$N" ]; then
  echo "Usage: $0 <number of packages to source> [<dataset dir>]"
  exit 1
fi

if [ -n "$2" ]; then
  DATASET_DIR="$2"
fi

docker build -t get-data "$PARENT_DIR"
docker run --name get-data get-data bash /source-packages.sh "$N"
RESULT=$?
docker stop get-data
if [ $RESULT -ne 0 ]; then
  echo "Failed to source packages"
  docker rm get-data
  exit 1
fi
docker cp get-data:/sources/. "$DATASET_DIR"