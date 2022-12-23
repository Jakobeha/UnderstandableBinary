# This image simply downloads and installs a bunch of packages (n packages) with source.
# We can later extract the source and compiled binaries
FROM debian:stable-slim
LABEL maintainer="Jakob Hain <jakobeha@gmail.com>"

# Add sources list
ADD deb-sources.list /etc/apt/sources.list
# Add source-packages script
ADD source-packages.sh /source-packages.sh

# Refresh package index
RUN apt-get update --allow-unauthenticated && apt-get upgrade -y --allow-unauthenticated

# Install source-packages.sh dependencies
RUN apt-get install dpkg-dev -y --allow-unauthenticated