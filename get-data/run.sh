N="$1"
if [ -z "$N" ]; then
  echo "Usage: $0 <number of packages to install>"
  exit 1
fi

docker build -t get-data . --build-args N="$1"
docker create --name get-data get-data
docker cp get-data:/data ../local/raw-sources
cd preprocessor && cargo run --release -- ../local/raw-sources ../local/examples
rm -rf ../local/raw-sources