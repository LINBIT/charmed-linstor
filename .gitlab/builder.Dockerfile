FROM ubuntu:focal

ARG CHARMCRAFT_VERSION=1.6.0
RUN apt-get update \
  && apt-get install -y python3-apt python3-pip python3-wheel python3-setuptools python3-dev python3-venv \
  && pip3 install -r https://raw.githubusercontent.com/canonical/charmcraft/$CHARMCRAFT_VERSION/requirements.txt \
  && pip3 install charmcraft==$CHARMCRAFT_VERSION \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
