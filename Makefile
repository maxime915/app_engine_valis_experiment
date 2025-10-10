VERSION := $(shell grep -m 1 '^version' pyproject.toml | sed 's/.*=[[:space:]]*["'\'']\([^"\'']*\)["'\''].*/\1/')
SRCS := $(shell find src -type f)
CFGS := pyproject.toml Dockerfile LICENSE Makefile README.md script.py

zip:	app_engine_valis_exp-$(VERSION).tar descriptor
	zip app_engine_valis_exp.zip descriptor.yaml app_engine_valis_exp-$(VERSION).tar

tmp_descriptor := descriptor.yaml.tmp
descriptor: pyproject.toml
	python3 -c 'import yaml;f=open("descriptor.yaml");y=yaml.safe_load(f);y["configuration"]["image"]["file"] = "/app_engine_valis_exp-$(VERSION).tar";y["version"] = "$(VERSION)"; print(yaml.dump(y, default_flow_style=False, sort_keys=False))' > $(tmp_descriptor)
	mv $(tmp_descriptor) descriptor.yaml

app_engine_valis_exp-$(VERSION).tar: $(SRCS) $(CFGS)
	docker build -t app-engine-valis-exp:$(VERSION) -f Dockerfile .
	docker save app-engine-valis-exp:$(VERSION) -o app_engine_valis_exp-$(VERSION).tar

.PHONY: zip descriptor
