# This image simply downloads and installs a bunch of packages (n packages) with source.
# We can later extract the source and compiled binaries
FROM debian:stable-slim
LABEL maintainer="Jakob Hain <jakobeha@gmail.com>"
ARG N=100

# Add sources list
ADD deb-sources.list /etc/apt/sources.list
# Add install-packages script
ADD install-packages.sh /install-packages.sh

# Refresh package index
RUN apt-get update --allow-unauthenticated && apt-get upgrade -y --allow-unauthenticated

# Install packages
RUN ./install-packages.sh $N