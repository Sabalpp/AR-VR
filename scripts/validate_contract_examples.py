#!/usr/bin/env python3
"""Validate checked-in examples; install jsonschema in the verification environment."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
root = Path(__file__).resolve().parents[1]
schema = json.loads((root/'contracts/websocket.v1.schema.json').read_text())
Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema,format_checker=FormatChecker())
examples=json.loads((root/'contracts/websocket.v1.examples.json').read_text())
for example in examples:
    validator.validate(example)
print(f'Validated {len(examples)} protocol examples against WebSocket v1 schema.')
