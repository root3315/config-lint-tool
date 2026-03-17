#!/usr/bin/env python3
"""
Config Lint Tool - Validate configuration files before deployment.
Supports JSON, YAML, INI, and TOML formats with comprehensive error checking.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import tomli
    TOML_AVAILABLE = True
except ImportError:
    try:
        import tomllib as tomli
        TOML_AVAILABLE = True
    except ImportError:
        TOML_AVAILABLE = False


class LintResult:
    """Represents a single linting error or warning."""
    
    def __init__(self, level: str, line: Optional[int], message: str, context: str = ""):
        self.level = level
        self.line = line
        self.message = message
        self.context = context
    
    def __str__(self) -> str:
        location = f"line {self.line}" if self.line else "unknown line"
        ctx = f": {self.context}" if self.context else ""
        return f"[{self.level.upper()}] {location} - {self.message}{ctx}"


class ConfigLinter:
    """Main linter class for configuration files."""
    
    COMMON_MISTAKES = {
        'localhost': 'Using localhost in production config',
        'password': 'Potential hardcoded password detected',
        'secret': 'Potential hardcoded secret detected',
        'api_key': 'Potential hardcoded API key detected',
        '127.0.0.1': 'Using loopback address in config',
        'debug': 'Debug mode may be enabled',
        'test': 'Test environment reference detected',
    }
    
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.results: List[LintResult] = []
    
    def lint_file(self, filepath: str) -> List[LintResult]:
        """Lint a single configuration file."""
        self.results = []
        path = Path(filepath)
        
        if not path.exists():
            self.results.append(LintResult('error', None, f"File not found: {filepath}"))
            return self.results
        
        if not path.is_file():
            self.results.append(LintResult('error', None, f"Not a file: {filepath}"))
            return self.results
        
        suffix = path.suffix.lower()
        
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as e:
            self.results.append(LintResult('error', None, f"Cannot read file (encoding issue): {e}"))
            return self.results
        except PermissionError:
            self.results.append(LintResult('error', None, f"Permission denied: {filepath}"))
            return self.results
        
        if not content.strip():
            self.results.append(LintResult('warning', 1, "File is empty or contains only whitespace"))
            return self.results
        
        self._check_file_size(path, filepath)
        self._check_sensitive_data(content)
        self._check_trailing_whitespace(content)
        
        if suffix in ('.json',):
            self._lint_json(content, filepath)
        elif suffix in ('.yaml', '.yml'):
            self._lint_yaml(content, filepath)
        elif suffix in ('.ini', '.cfg', '.conf'):
            self._lint_ini(content, filepath)
        elif suffix in ('.toml',):
            self._lint_toml(content, filepath)
        else:
            self.results.append(LintResult('warning', None, f"Unknown config format: {suffix}"))
        
        return self.results
    
    def _check_file_size(self, path: Path, filepath: str) -> None:
        """Check if config file is unusually large."""
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 10:
            self.results.append(LintResult('warning', None, f"Config file is large ({size_mb:.1f}MB)"))
    
    def _check_sensitive_data(self, content: str) -> None:
        """Check for potential sensitive data in config."""
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            for pattern, message in self.COMMON_MISTAKES.items():
                if pattern in line_lower and '=' in line or ':' in line:
                    if 'example' not in line_lower and 'placeholder' not in line_lower:
                        self.results.append(LintResult('warning', line_num, message, line.strip()[:50]))
    
    def _check_trailing_whitespace(self, content: str) -> None:
        """Check for trailing whitespace."""
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            if line != line.rstrip():
                self.results.append(LintResult('warning', line_num, "Trailing whitespace detected"))
    
    def _lint_json(self, content: str, filepath: str) -> None:
        """Lint JSON configuration file."""
        lines = content.split('\n')
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            self.results.append(LintResult('error', e.lineno, f"JSON syntax error: {e.msg}"))
            return
        
        self._check_json_structure(data, 1)
        
        if isinstance(data, dict):
            if len(data) == 0:
                self.results.append(LintResult('warning', 1, "Empty JSON object"))
    
    def _check_json_structure(self, data: Any, base_line: int) -> None:
        """Recursively check JSON structure for issues."""
        if isinstance(data, dict):
            keys = list(data.keys())
            if len(keys) != len(set(keys)):
                self.results.append(LintResult('error', base_line, "Duplicate keys detected"))
            
            for key, value in data.items():
                if key.startswith('_') and self.strict:
                    self.results.append(LintResult('warning', base_line, f"Private key '{key}' in config"))
                self._check_json_structure(value, base_line)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._check_json_structure(item, base_line)
    
    def _lint_yaml(self, content: str, filepath: str) -> None:
        """Lint YAML configuration file."""
        if not YAML_AVAILABLE:
            self.results.append(LintResult('error', None, "YAML support not available. Install PyYAML: pip install pyyaml"))
            return
        
        lines = content.split('\n')
        
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            if hasattr(e, 'problem_mark'):
                line = e.problem_mark.line + 1
                self.results.append(LintResult('error', line, f"YAML syntax error: {e.problem}"))
            else:
                self.results.append(LintResult('error', None, f"YAML syntax error: {str(e)}"))
            return
        
        if data is None:
            self.results.append(LintResult('warning', 1, "Empty YAML document"))
            return
        
        self._check_yaml_anchors(content, lines)
    
    def _check_yaml_anchors(self, content: str, lines: List[str]) -> None:
        """Check for YAML-specific issues."""
        for line_num, line in enumerate(lines, 1):
            if re.search(r'&\w+', line) and not re.search(r'\*\w+', content):
                self.results.append(LintResult('warning', line_num, "Anchor defined but no reference found"))
            
            if line.strip().startswith('!!!'):
                self.results.append(LintResult('warning', line_num, "Explicit YAML tag used"))
    
    def _lint_ini(self, content: str, filepath: str) -> None:
        """Lint INI configuration file."""
        import configparser
        from io import StringIO
        
        lines = content.split('\n')
        config = configparser.ConfigParser()
        
        try:
            config.read_string(content)
        except configparser.Error as e:
            self.results.append(LintResult('error', getattr(e, 'lineno', None), f"INI syntax error: {e}"))
            return
        
        sections = config.sections()
        
        if not sections:
            if not config.defaults():
                self.results.append(LintResult('warning', 1, "Empty INI file - no sections or defaults"))
        
        for section in sections:
            if section.lower() in ('default', 'main', 'general'):
                continue
            
            items = dict(config.items(section))
            if not items:
                section_line = self._find_section_line(lines, section)
                self.results.append(LintResult('warning', section_line, f"Section [{section}] is empty"))
    
    def _find_section_line(self, lines: List[str], section: str) -> Optional[int]:
        """Find the line number of a section."""
        for line_num, line in enumerate(lines, 1):
            if line.strip().lower() == f'[{section.lower()}]':
                return line_num
        return None
    
    def _lint_toml(self, content: str, filepath: str) -> None:
        """Lint TOML configuration file."""
        if not TOML_AVAILABLE:
            self.results.append(LintResult('error', None, "TOML support not available. Install tomli: pip install tomli"))
            return
        
        lines = content.split('\n')
        
        try:
            data = tomli.loads(content)
        except tomli.TOMLDecodeError as e:
            self.results.append(LintResult('error', None, f"TOML syntax error: {e}"))
            return
        
        if not data:
            self.results.append(LintResult('warning', 1, "Empty TOML document"))
    
    def get_summary(self) -> str:
        """Get a summary of lint results."""
        errors = sum(1 for r in self.results if r.level == 'error')
        warnings = sum(1 for r in self.results if r.level == 'warning')
        
        parts = []
        if errors:
            parts.append(f"{errors} error(s)")
        if warnings:
            parts.append(f"{warnings} warning(s)")
        
        if not parts:
            return "No issues found"
        
        return ", ".join(parts)
    
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(r.level == 'error' for r in self.results)


def find_config_files(directory: str, patterns: Optional[List[str]] = None) -> List[str]:
    """Find configuration files in a directory."""
    if patterns is None:
        patterns = ['*.json', '*.yaml', '*.yml', '*.ini', '*.cfg', '*.conf', '*.toml']
    
    config_files = []
    dir_path = Path(directory)
    
    if not dir_path.exists():
        return []
    
    for pattern in patterns:
        config_files.extend(dir_path.glob(f'**/{pattern}'))
    
    return sorted(set(str(f) for f in config_files))


def format_output(results: List[LintResult], filepath: str, format_type: str) -> str:
    """Format lint results for output."""
    output_lines = []
    
    if format_type == 'json':
        output_data = {
            'file': filepath,
            'issues': [
                {
                    'level': r.level,
                    'line': r.line,
                    'message': r.message,
                    'context': r.context
                }
                for r in results
            ]
        }
        return json.dumps(output_data, indent=2)
    
    elif format_type == 'github':
        for r in results:
            level = 'error' if r.level == 'error' else 'warning'
            line = r.line or 1
            output_lines.append(f"::{level} file={filepath},line={line}::{r.message}")
        return '\n'.join(output_lines)
    
    else:
        output_lines.append(f"\n{filepath}:")
        for r in results:
            output_lines.append(f"  {r}")
        return '\n'.join(output_lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Lint configuration files and catch errors before deployment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s config.json
  %(prog)s --recursive ./configs
  %(prog)s --format github *.yaml
  %(prog)s --strict app.toml
'''
    )
    
    parser.add_argument('files', nargs='*', help='Config files to lint')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='Recursively find config files in directories')
    parser.add_argument('-s', '--strict', action='store_true',
                        help='Enable strict mode (more warnings)')
    parser.add_argument('-f', '--format', choices=['text', 'json', 'github'],
                        default='text', help='Output format')
    parser.add_argument('--exclude', nargs='+', default=[],
                        help='Patterns to exclude')
    
    args = parser.parse_args()
    
    if not args.files:
        parser.print_help()
        return 1
    
    all_files = []
    for item in args.files:
        if os.path.isdir(item) and args.recursive:
            all_files.extend(find_config_files(item))
        else:
            all_files.append(item)
    
    for pattern in args.exclude:
        all_files = [f for f in all_files if not re.search(pattern, f)]
    
    linter = ConfigLinter(strict=args.strict)
    total_errors = 0
    total_warnings = 0
    
    for filepath in all_files:
        results = linter.lint_file(filepath)
        
        if args.format != 'text' or results:
            print(format_output(results, filepath, args.format))
        
        total_errors += sum(1 for r in results if r.level == 'error')
        total_warnings += sum(1 for r in results if r.level == 'warning')
    
    if args.format == 'text':
        print(f"\n--- Summary ---")
        print(f"Files checked: {len(all_files)}")
        print(f"Total: {total_errors} error(s), {total_warnings} warning(s)")
    
    return 1 if total_errors > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
