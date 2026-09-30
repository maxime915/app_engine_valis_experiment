NAME := $(shell sed -n 's/^name_short:[[:space:]]*//p' descriptor.yaml)
VERSION := $(shell sed -n 's/^version:[[:space:]]*//p' descriptor.yaml)
IMAGE_FILE := $(shell sed -n 's/^    file:[[:space:]]*//p' descriptor.yaml)
SRCS := $(shell find src -type f)
CFGS := pyproject.toml Dockerfile LICENSE Makefile README.md script.py

PIGZ := $(shell command -v pigz 2>/dev/null)

# JSON schema referenced by the descriptor, cached locally (keyed by URL)
SCHEMA_URL := $(shell sed -n 's/^\$$schema:[[:space:]]*//p' descriptor.yaml)
SCHEMA_CACHE := .cache/schema-$(shell printf '%s' '$(SCHEMA_URL)' | md5sum | cut -c1-12).json
VALIDATE_PY := uv run --no-project -q --with jsonschema --with pyyaml python


zip: $(NAME).zip

$(NAME).zip:	descriptor logo.png $(NAME)-$(VERSION).tar
ifdef PIGZ
	rm -f $(NAME).zip
	pigz -K -p $(shell nproc) -c $(NAME)-$(VERSION).tar > $(NAME).zip
	zip $(NAME).zip descriptor.yaml logo.png
else
	rm -f $(NAME).zip
	zip $(NAME).zip $(NAME)-$(VERSION).tar descriptor.yaml logo.png
endif

descriptor: $(SCHEMA_CACHE)
	@$(VALIDATE_PY) tools/validate_descriptor.py descriptor.yaml $(SCHEMA_CACHE)
	@test "$(IMAGE_FILE)" = "/$(NAME)-$(VERSION).tar" || \
		{ echo "descriptor.yaml: image file is '$(IMAGE_FILE)', expected '/$(NAME)-$(VERSION).tar'" >&2; exit 1; }
	@echo "descriptor.yaml: valid"

$(SCHEMA_CACHE):
	@test -n "$(SCHEMA_URL)" || { echo "descriptor.yaml: missing \$$schema" >&2; exit 1; }
	@mkdir -p $(@D)
	curl -fsSL "$(SCHEMA_URL)" -o $@.tmp && mv $@.tmp $@

$(NAME)-$(VERSION).tar: $(SRCS) $(CFGS)
	docker build -t app-engine-valis-exp:$(VERSION) -f Dockerfile .
	docker save app-engine-valis-exp:$(VERSION) -o $(NAME)-$(VERSION).tar

.PHONY: zip descriptor
