# Claude Code Project Instructions

## Project Overview

This is a Python CLI tool that monitors xarray's upstream dependency CI tests for zarr compatibility. It analyzes GitHub Actions workflow runs to determine if zarr changes are breaking xarray's tests.

## Development Commands

### Linting and Formatting
```bash
uv run ruff check .
uv run ruff format .
```

### Testing Installation
```bash
uv tool install -e .
xarray-upstream-checker --help
xarray-upstream-checker
```

### Pre-commit Hooks
```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Code Structure

- `src/xarray_upstream_checker/` - Main package directory
  - `main.py` - CLI entry point with argparse
  - `checker.py` - Core ZarrUpstreamChecker class
  - `display.py` - Rich formatting and display logic
  - `exceptions.py` - Custom exception classes
  - `__init__.py` - Package initialization

## Key Dependencies

- `rich` - Terminal formatting and displays
- `setuptools` - Build backend (better than hatchling for editable installs)
- GitHub CLI (`gh`) - Required for accessing workflow data

## Git Workflow

- Use specific `git add` commands, not `git add .`
- Commit frequently with descriptive messages
- Pre-commit hooks will auto-format code

## Important Notes

- Always use `uv run` prefix for Python commands
- The tool requires GitHub CLI to be installed and authenticated
- Source layout structure with `src/` is intentional for proper packaging
- CLI should show help without running the main script logic
