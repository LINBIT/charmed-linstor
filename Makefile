SERIES ?= ubuntu-20.04
ARCHS ?= amd64-arm64
CHARMS := $(addsuffix _$(SERIES)-$(ARCHS).charm,$(dir $(wildcard */metadata.yaml)))

all: $(CHARMS) bundle

.PHONY: %.charm clean
%_$(SERIES)-$(ARCHS).charm:
	charmcraft pack -p $*

bundle:
	charmcraft pack -p linstor
