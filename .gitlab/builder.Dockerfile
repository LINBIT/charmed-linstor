FROM ubuntu:20.04

RUN apt-get update \
  && apt-get install -y xz-utils curl python3-pip jq \
  && curl -fsSL https://launchpad.net/juju/2.9/2.9.7/+download/juju-2.9.7-linux-amd64.tar.xz | tar -xvJC /usr/local/bin \
  && curl -fsSL https://dl.k8s.io/release/v1.21.2/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl \
  && chmod +x /usr/local/bin/kubectl \
  && pip3 install charmcraft==1.0.0 \
  && rm -r /var/cache/apt/*
