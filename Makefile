NAME := $(shell sed -n 's/^name_short:[[:space:]]*//p' descriptor.yaml)
VERSION := $(shell sed -n 's/^version:[[:space:]]*//p' descriptor.yaml)
IMAGE_FILE := $(shell sed -n 's/^    file:[[:space:]]*//p' descriptor.yaml)
SRCS := $(shell find src -type f)
CFGS := pyproject.toml Dockerfile LICENSE Makefile README.md script.py

PIGZ := $(shell command -v pigz 2>/dev/null)


zip: $(NAME).zip

$(NAME).zip:	descriptor $(NAME)-$(VERSION).tar
ifdef PIGZ
	rm -f $(NAME).zip
	pigz -K -p $(shell nproc) -c $(NAME)-$(VERSION).tar > $(NAME).zip
	zip $(NAME).zip descriptor.yaml
else
	rm -f $(NAME).zip
	zip $(NAME).zip $(NAME)-$(VERSION).tar descriptor.yaml
endif

descriptor:
	@test "$(IMAGE_FILE)" = "/$(NAME)-$(VERSION).tar" || \
		{ echo "descriptor.yaml: image file is '$(IMAGE_FILE)', expected '/$(NAME)-$(VERSION).tar'" >&2; exit 1; }

$(NAME)-$(VERSION).tar: $(SRCS) $(CFGS)
	docker build -t app-engine-valis-exp:$(VERSION) -f Dockerfile .
	docker save app-engine-valis-exp:$(VERSION) -o $(NAME)-$(VERSION).tar

.PHONY: zip descriptor
