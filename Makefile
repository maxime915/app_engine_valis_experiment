VERSION := $(shell grep -m 1 '^version' pyproject.toml | sed 's/.*=[[:space:]]*["'\'']\([^"\'']*\)["'\''].*/\1/')
SRCS := $(shell find src -type f)
CFGS := pyproject.toml Dockerfile LICENSE Makefile README.md script.py

zip:	app_engine_valis_exp-$(VERSION).tar descriptor
	rm -f app_engine_valis_exp.zip
	pigz -K -p $(shell nproc) -c app_engine_valis_exp-$(VERSION).tar > app_engine_valis_exp.zip
	zip app_engine_valis_exp.zip descriptor.yaml

tmp_descriptor := descriptor.yaml.tmp
descriptor: pyproject.toml
	python3 -c 'import yaml;f=open("descriptor.yaml");y=yaml.safe_load(f);y["configuration"]["image"]["file"] = "/app_engine_valis_exp-$(VERSION).tar";y["version"] = "$(VERSION)"; print(yaml.dump(y, default_flow_style=False, sort_keys=False), end="")' > $(tmp_descriptor)
	mv $(tmp_descriptor) descriptor.yaml

app_engine_valis_exp-$(VERSION).tar: $(SRCS) $(CFGS)
	docker build -t app-engine-valis-exp:$(VERSION) -f Dockerfile .
	docker save app-engine-valis-exp:$(VERSION) -o app_engine_valis_exp-$(VERSION).tar

.PHONY: zip descriptor
