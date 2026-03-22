# config-lint-tool

Catch config errors before they break your deploy.

## Why

We've all been there - a typo in the config, a missing bracket, hardcoded secrets that slipped through. This tool checks your config files before they hit production.

## What it does

- Validates syntax for JSON, YAML, INI, and TOML files
- Detects potential sensitive data (passwords, API keys, secrets)
- Finds trailing whitespace and formatting issues
- Warns about localhost/127.0.0.1 in configs
- Checks for empty sections and suspicious patterns
- **Validates configs against JSON Schema**
- **Nested structure validation (depth limits, empty objects/arrays)**
- GitHub Actions compatible output format

## Install

```bash
pip install -r requirements.txt
```

Or just run it with Python if you only need JSON/INI support.

## Usage

Basic linting:
```bash
python config_lint.py config.json
python config_lint.py app.yaml database.ini
```

Recursive directory scan:
```bash
python config_lint.py -r ./configs
```

Strict mode (more warnings):
```bash
python config_lint.py --strict production.toml
```

Schema validation:
```bash
python config_lint.py --schema config_schema.json config.json
python config_lint.py --schema schema.json -r ./configs
```

Nested depth control:
```bash
python config_lint.py --max-depth 5 config.json
```

GitHub Actions format:
```bash
python config_lint.py -f github *.yaml
```

JSON output for CI:
```bash
python config_lint.py -f json config.json
```

Exclude patterns:
```bash
python config_lint.py -r ./configs --exclude "test_" "example"
```

## Exit codes

- `0` - All good, no errors
- `1` - Errors found or no files provided

Warnings don't fail the build, only errors do.

## Supported formats

| Format | Extensions | Notes |
|--------|------------|-------|
| JSON | `.json` | Built-in |
| YAML | `.yaml`, `.yml` | Needs PyYAML |
| INI | `.ini`, `.cfg`, `.conf` | Built-in |
| TOML | `.toml` | Needs tomli |

## Nested Structure Validation

The tool validates nested config structures and reports issues like:

- **Excessive nesting depth** - Warns when config exceeds maximum depth (default: 10)
- **Empty objects/arrays** - Detects unused nested structures
- **Empty string values** - Flags potentially misconfigured keys
- **Null values in arrays** - Warns about null items in lists
- **Private keys** - In strict mode, warns about keys starting with `_`

Control the maximum nesting depth:

```bash
python config_lint.py --max-depth 5 deeply_nested.json
```

## Schema Validation

Validate your configs against a JSON Schema to ensure required fields are present and values match expected types.

Create a schema file:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["database", "port"],
  "properties": {
    "database": {
      "type": "object",
      "required": ["host", "port"],
      "properties": {
        "host": {
          "type": "string",
          "minLength": 1
        },
        "port": {
          "type": "integer",
          "minimum": 1,
          "maximum": 65535
        }
      }
    },
    "port": {
      "type": "integer",
      "minimum": 1,
      "maximum": 65535
    },
    "debug": {
      "type": "boolean"
    },
    "log_level": {
      "type": "string",
      "enum": ["debug", "info", "warning", "error"]
    }
  }
}
```

Then validate:

```bash
python config_lint.py --schema schema.json config.json
```

Schema validation errors are reported with full nested paths (e.g., `database.host`, `servers[0].name`) and will fail the lint.

## Example output

```
config.json:
  [WARNING] line 5 - Potential hardcoded password detected: password = "supersecret123"
  [WARNING] line 12 - Trailing whitespace detected
  [WARNING] line 18 - Empty object at 'deprecated_settings'
  [WARNING] line 22 - Excessive nesting depth (12) at 'a.b.c.d.e.f.g.h.i.j.k.l'
  [ERROR] line 25 - JSON syntax error: Expecting ',' delimiter
  [ERROR] root - Schema validation failed at 'database.port': Type mismatch: expected integer, got string

--- Summary ---
Files checked: 1
Total: 2 error(s), 3 warning(s)
```

## CI/CD integration

GitHub Actions:
```yaml
- name: Lint configs
  run: python config_lint.py -f github -r ./configs
```

GitLab CI:
```yaml
lint-configs:
  script:
    - python config_lint.py -r ./configs
```

Pre-commit hook:
```bash
#!/bin/bash
python config_lint.py -r configs/ || exit 1
```

## Limitations

- Schema validation only supports JSON, YAML, and TOML formats
- No cross-file reference checking
- TOML requires Python 3.11+ or tomli package

## License

MIT
