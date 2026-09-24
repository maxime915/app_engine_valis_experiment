VERSION := $(shell grep -m 1 '^version' pyproject.toml | sed 's/.*=[[:space:]]*["'\'']\([^"\'']*\)["'\''].*/\1/')
SRCS := $(shell find src -type f)
CFGS := pyproject.toml Dockerfile LICENSE Makefile README.md script.py

PIGZ := $(shell command -v pigz 2>/dev/null)

zip:	app_engine_valis_exp-$(VERSION).tar descriptor
ifdef PIGZ
	rm -f app_engine_valis_exp.zip
	pigz -K -p $(shell nproc) -c app_engine_valis_exp-$(VERSION).tar > app_engine_valis_exp.zip
	zip app_engine_valis_exp.zip descriptor.yaml
else
	rm -f app_engine_valis_exp.zip
	zip app_engine_valis_exp.zip app_engine_valis_exp-$(VERSION).tar descriptor.yaml
endif

tmp_descriptor := descriptor.yaml.tmp
descriptor: pyproject.toml
	sed \
		-e 's|^version: .*|version: $(VERSION)|' \
		-e 's|file: /app_engine_valis_exp-.*\.tar$$|file: /app_engine_valis_exp-$(VERSION).tar|' \
		descriptor.yaml > $(tmp_descriptor)
	mv $(tmp_descriptor) descriptor.yaml

app_engine_valis_exp-$(VERSION).tar: $(SRCS) $(CFGS)
	docker build -t app-engine-valis-exp:$(VERSION) -f Dockerfile .
	docker save app-engine-valis-exp:$(VERSION) -o app_engine_valis_exp-$(VERSION).tar

.PHONY: zip descriptor
