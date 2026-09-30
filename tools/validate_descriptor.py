# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "jsonschema",
#     "pyyaml",
# ]
# ///
"validate a task descriptor (YAML) against a JSON schema file"

import argparse
import copy
import json
import sys
from types import SimpleNamespace

import jsonschema
import yaml

# parameters are composed from partial schemas (allOf/oneOf/$ref): these only
# see their own keywords, so strictness is enforced at the composed roots
PARTIAL_SCHEMAS = (
    "#/$defs/io/base_parameter",
    "#/$defs/io/typed_parameter",
    "#/$defs/io/input_parameter",
    "#/$defs/io/output_parameter",
)
COMPOSED_ROOTS = ("#/$defs/io/input_parameter", "#/$defs/io/output_parameter")


def _resolve(schema: dict, pointer: str):
    node = schema
    for part in pointer.removeprefix("#/").split("/"):
        node = node[int(part) if isinstance(node, list) else part]
    return node


def _patch_upstream_gaps(schema: dict):
    """declare keys that the upstream schema accepts but does not describe

    Each patch is only applied while the corresponding gap is present.
    """
    configuration = _resolve(schema, "#/properties/configuration/properties")
    # documented as required, but missing from the schema
    configuration.setdefault(
        "image",
        {
            "type": "object",
            "required": ["file"],
            "properties": {"file": {"$ref": "#/$defs/types/path"}},
        },
    )

    # upstream declares a property literally named "$ref" instead of derived_from
    try:
        dependencies = _resolve(
            schema, "#/$defs/io/output_parameter/allOf/1/properties/dependencies"
        )
    except (KeyError, IndexError):
        return
    if "$ref" in dependencies.get("properties", {}):
        dependencies["properties"] = {
            "derived_from": {"$ref": "#/$defs/dependencies/derived_from"}
        }


def make_strict(schema: dict) -> dict:
    """return a copy of schema that rejects properties it does not declare

    The upstream schema allows unknown keys almost everywhere, so typos
    (e.g. `cpu` instead of `cpus`) go unnoticed.
    """
    schema = copy.deepcopy(schema)
    _patch_upstream_gaps(schema)
    partials = {id(_resolve(schema, pointer)) for pointer in PARTIAL_SCHEMAS}

    def walk(node, partial: bool):
        if isinstance(node, list):
            for value in node:
                walk(value, partial)
            return
        if not isinstance(node, dict):
            return

        partial = partial or id(node) in partials
        if node.get("unevaluatedProperties") is True:
            del node["unevaluatedProperties"]
        if (
            "properties" in node
            and not partial
            and "additionalProperties" not in node
            and "unevaluatedProperties" not in node
        ):
            node["unevaluatedProperties"] = False

        for key, value in node.items():
            # the value of a declared property is a complete object again
            if key in ("properties", "patternProperties", "$defs"):
                for sub in value.values():
                    walk(sub, False)
            else:
                walk(value, partial)

    walk(schema, False)
    for pointer in COMPOSED_ROOTS:
        _resolve(schema, pointer)["unevaluatedProperties"] = False
    return schema


def _causes(error) -> list:
    """leaf errors of the alternatives that were meant to match

    Alternatives failing on a `const` check (e.g. `type.id` mismatch) or
    whose value has the wrong shape were not the intended one and are
    ignored, unless all are.
    """
    if not error.context:
        return [error]
    branches: dict = {}
    for sub in error.context:
        branches.setdefault(sub.relative_schema_path[0], []).extend(_causes(sub))

    def mismatched(leaf):
        "whether this leaf shows the alternative is not the intended one"
        if leaf.validator == "const":
            return True
        # wrong shape, e.g. short (string) form vs long (object) form
        return leaf.validator == "type" and leaf.validator_value in ("object", "array")

    relevant = [
        leaves for leaves in branches.values() if not any(map(mismatched, leaves))
    ]
    if relevant:
        return [leaf for leaves in relevant for leaf in leaves]

    # nothing matched (e.g. unknown type id): summarize the accepted values
    consts = [
        leaf for leaves in branches.values() for leaf in leaves if leaf.validator == "const"
    ]
    if not consts:
        return [leaf for leaves in branches.values() for leaf in leaves]
    deepest = max(consts, key=lambda leaf: len(leaf.absolute_path))
    accepted = set().union(
        *(c.accepted if hasattr(c, "accepted") else {c.validator_value} for c in consts)
    )
    return [
        SimpleNamespace(
            json_path=deepest.json_path,
            absolute_path=deepest.absolute_path,
            instance=deepest.instance,
            validator="const",
            accepted=accepted,
            message=f"{deepest.instance!r} is not one of "
            + ", ".join(sorted(map(repr, accepted))),
        )
    ]


def _explain(errors: list):
    """replace composition failures by their most relevant causes

    When a parameter matches none of its alternatives, its keys are also
    reported as unevaluated: this follow-up error is dropped as it only
    restates the failure.
    """
    failed_paths = {e.json_path for e in errors if e.context}
    seen = set()
    for error in errors:
        if error.context:
            causes = _causes(error)
        elif error.validator == "unevaluatedProperties" and error.json_path in failed_paths:
            continue
        else:
            causes = [error]
        for cause in causes:
            if (cause.json_path, cause.message) not in seen:
                seen.add((cause.json_path, cause.message))
                yield cause


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("descriptor")
    parser.add_argument("schema")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="reject properties that are not declared in the schema",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="KEY",
        help="top-level key tolerated in strict mode (repeatable)",
    )
    args = parser.parse_args()

    with open(args.schema, "r", encoding="utf8") as schema_f:
        schema = json.load(schema_f)
    with open(args.descriptor, "r", encoding="utf8") as descriptor_f:
        descriptor = yaml.safe_load(descriptor_f)

    if args.strict:
        schema = make_strict(schema)
        schema.setdefault("properties", {}).update({key: True for key in args.allow})

    validator = jsonschema.Draft201909Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    errors = sorted(validator.iter_errors(descriptor), key=lambda e: e.json_path)
    for error in _explain(errors):
        print(f"{args.descriptor}: {error.json_path}: {error.message}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
