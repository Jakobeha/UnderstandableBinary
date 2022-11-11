# This image simply downloads and installs a bunch of packages (n packages) with source.
# We can later extract the source and compiled binaries
ARG N=10

FROM debian:stable-slim
LABEL maintainer="Jakob Hain <jakobeha@gmail.com>"
# Add deb-src
ADD deb-sources.list /etc/apt/sources.list
# Add other files from host
ADD install-packages.sh /install-packages.sh
ADD scraper /scraper

# Refresh package index
RUN apt-get update --allow-unauthenticated && apt-get upgrade -y --allow-unauthenticated


# Install Rust
RUN apt-get install curl apt-utils build-essential -y --allow-unauthenticated
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    RUST_VERSION=1.65.0
RUN set -eux; \
    curl -sSLf "https://static.rust-lang.org/rustup/archive/1.20.2/x86_64-unknown-linux-gnu/rustup-init" -o rustup-init; \
    echo 'e68f193542c68ce83c449809d2cad262cc2bbb99640eb47c58fc1dc58cc30add *rustup-init' | sha256sum -c -; \
    chmod +x rustup-init; \
    ./rustup-init -y -q --no-modify-path --profile minimal --component rustfmt --component clippy --default-toolchain "$RUST_VERSION"; \
    rm -f rustup-init; \
    chmod -R a+w "$RUSTUP_HOME" "$CARGO_HOME"

# Build scraper
RUN cd /scraper && cargo build

# Install packages
RUN ./install-packages.sh $N

# Run scraper
RUN cd /scraper && cargo run -- /sources /data