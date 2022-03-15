FROM ubuntu:20.04

RUN apt-get update \
  && apt-get install -y xz-utils curl python3-pip python3-apt jq \
  && curl -fsSL https://launchpad.net/juju/2.9/2.9.26/+download/juju-2.9.26-linux-amd64.tar.xz | tar -xvJC /usr/local/bin \
  && curl -fsSL https://dl.k8s.io/release/$(curl -fsSL https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl \
  && chmod +x /usr/local/bin/kubectl \
  && pip3 install charmcraft==1.5.0 \
  && rm -r /var/cache/apt/*
