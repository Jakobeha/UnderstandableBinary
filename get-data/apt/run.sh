PARENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
NUM_PACKAGES=4294967295
INSTALL_DIR=$PARENT_DIR/../../../UnderstandableBinary-data/apt
RECREATE=0

# Show help if necessary
function show_help() {
  usage="Usage: $0 [-n NUM_PACKAGES] [-o INSTALL_DIR] [-f]

Download and build the packages from the APT repository

    -n NUM_PACKAGES  Number of packages to install. Default: all
    -o INSTALL_DIR   Directory where the packages are installed. Default: $INSTALL_DIR
    -f               Recreate the Docker image and container.
                     Otherwise we will resume the current container (e.g. if it exited early) Default: false"
  echo "$usage"
}

# Process options
OPTIND=1
while getopts "h?n:o:f" opt; do
  case "$opt" in
    h|\?)
      show_help
      exit 0
      ;;
    n)  NUM_PACKAGES=$OPTARG
      ;;
    o)  INSTALL_DIR=$OPTARG
      ;;
    f)  RECREATE=1
      ;;
  esac
done
shift $((OPTIND-1))
[ "${1:-}" = "--" ] && shift

EXISTS=$(docker ps -aq -f name=get-data)
IMG_EXISTS=$(docker images -q get-data)
if [ "$EXISTS" ] && [ "$RECREATE" -eq 1 ]; then
  echo "** Container already exists, deleting..."
  docker rm -f get-data
  if [ "$IMG_EXISTS" ]; then
    docker rmi get-data
    IMG_EXISTS=""
  fi
  EXISTS=""
fi

if [ "$EXISTS" ]; then
  echo "** Container already exists, resuming..."
  if [ "$(docker ps -aq -f status=exited -f name=get-data)" ]; then
    echo "** Container exited, restarting..."
    docker start get-data
  fi
  docker exec get-data bash /source-packages.sh "$NUM_PACKAGES"
  RESULT=$?
else
  if [ "$IMG_EXISTS" ]; then
    echo "** Creating image..."
    docker build -t get-data "$PARENT_DIR"
  fi
  echo "** Creating and running container..."
  docker run --name get-data get-data bash /source-packages.sh "$NUM_PACKAGES"
  RESULT=$?
fi
docker stop get-data
if [ $RESULT -ne 0 ]; then
  echo "Failed to source packages"
  exit 1
fi
# Note the '.' after '/data/' below. This is important, as it copies the contents of the directory, not the directory itself.
docker cp get-data:/data/. "$INSTALL_DIR"
