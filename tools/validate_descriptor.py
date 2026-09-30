# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "jsonschema",
#     "pyyaml",
# ]
# ///
"validate a task descriptor (YAML) against a JSON schema file"

import json
import sys

import jsonschema
import yaml


def main(descriptor_path: str, schema_path: str) -> int:
    with open(schema_path, "r", encoding="utf8") as schema_f:
        schema = json.load(schema_f)
    with open(descriptor_path, "r", encoding="utf8") as descriptor_f:
        descriptor = yaml.safe_load(descriptor_f)

    validator = jsonschema.Draft201909Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    errors = sorted(validator.iter_errors(descriptor), key=lambda e: e.json_path)
    for error in errors:
        print(f"{descriptor_path}: {error.json_path}: {error.message}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
