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

## Example output

```
config.json:
  [WARNING] line 5 - Potential hardcoded password detected: password = "supersecret123"
  [WARNING] line 12 - Trailing whitespace detected
  [ERROR] line 25 - JSON syntax error: Expecting ',' delimiter

--- Summary ---
Files checked: 1
Total: 1 error(s), 2 warning(s)
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

- Doesn't validate config schema (just syntax and common issues)
- No cross-file reference checking
- TOML requires Python 3.11+ or tomli package

## License

MIT
