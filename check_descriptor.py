import yaml
import json
from jsonschema import validate, ValidationError


def load_jsonschema(file_path):
    with open(file_path, "r") as schema:
        return json.load(schema)


def load_yaml_file(yaml_file_path):
    with open(yaml_file_path, "r") as file:
        return yaml.safe_load(file)


def validate_yaml_against_schema(yaml_file_path, schema_file_path):
    json_schema = load_jsonschema(schema_file_path)
    yaml_content = load_yaml_file(yaml_file_path)

    try:
        validate(instance=yaml_content, schema=json_schema)
        print("YAML file is valid against the schema.")
    except ValidationError as e:
        print("YAML file is invalid against the schema.")
        print(e)


validate_yaml_against_schema("valis-descriptor.yaml", "task.v0.json")
