# xarray-upstream-checker

Monitor xarray's upstream dependency CI tests for zarr compatibility.

This tool checks the most recent upstream-dev CI workflow run for xarray and reports on zarr compatibility status, version information, and test failures. It helps quickly identify whether upstream test failures are zarr-related or due to other upstream dependencies.

## Features

- 🔍 **Finds recent scheduled test runs** - Automatically locates the most recent run where upstream tests actually executed
- 📊 **Zarr version detection** - Extracts the exact zarr version being tested (e.g., `3.1.3.dev23+g62d1a6abc`)
- 🧪 **Test failure analysis** - Categorizes failures as zarr-related vs other upstream dependencies
- ⚡ **Rich output** - Beautiful, colorized terminal output with detailed breakdowns
- 🕐 **Freshness checking** - Compares workflow run time against latest zarr commits

## Installation

### Install as a uv tool (recommended)

```bash
uv tool install git+https://github.com/ianhi/xarray-upstream-checker.git
```

After installation, you can run:

```bash
xarray-upstream-checker
```

### Requirements

- [GitHub CLI (`gh`)](https://cli.github.com/) must be installed and authenticated
- Python 3.9+

To set up GitHub CLI:

```bash
# Install gh CLI (if not already installed)
# macOS
brew install gh
# Or see: https://cli.github.com/

# Authenticate
gh auth login
```

## Usage

Simply run the tool:

```bash
xarray-upstream-checker
```

### Example Output

```
Found 10 scheduled runs to check
✓ Found scheduled run with tests: 17750273614

┌─ 🔄 Most Recent Run With Tests ─────────────────────────────────────────────┐
│ Workflow Status: failure                                                    │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ 📦 Version Info ────────────────────────────────────────────────────────────┐
│ Zarr version tested: 3.1.3.dev23+g62d1a6abc                                  │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ 🧪 Test Failures (2 total) ────────────────────────────────────────────────┐
│ ┌─────────────────┬───────┬──────────────────────────────────────────────────┐ │
│ │ Category        │ Count │ Tests                                            │ │
│ ├─────────────────┼───────┼──────────────────────────────────────────────────┤ │
│ │ 🔧 Zarr-related │ 1     │ TestZarrDatatreeIO::test_zarr_encoding (Assert…) │ │
│ │ 📦 Other        │ 1     │ test_roundtrip_1d_pandas_extension_array (Ass…) │ │
│ └─────────────────┴───────┴──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ 📊 Failure Analysis ────────────────────────────────────────────────────────┐
│ 🔀 Mixed failures: both zarr and other upstream issues                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

## What it does

1. **Searches for priority runs** - Uses `--event schedule` and `--event workflow_dispatch` to find upstream test runs (not PR-triggered runs)
2. **Verifies test execution** - Distinguishes between "workflow ran but skipped tests" vs "tests actually executed"
3. **Extracts zarr version** - Parses workflow logs to find the exact zarr version tested
4. **Categorizes failures** - Analyzes test names to identify zarr-related vs other upstream dependency issues
5. **Provides actionable info** - Shows specific failed tests, error types, and manual workflow links

## How it works

The tool uses the GitHub CLI (`gh`) to:
- Query the xarray repository's workflow runs
- Filter for priority events (scheduled and workflow_dispatch) on the main branch
- Find the most recent run where upstream-dev tests actually executed (not skipped)
- Parse job logs to extract zarr version and test failure details
- Categorize failures based on test names and keywords

## Development

### Local Development

To contribute or modify:

```bash
git clone https://github.com/ianhi/xarray-upstream-checker.git
cd xarray-upstream-checker

# Install in editable mode for development
uv tool install -e .

# Run the tool
xarray-upstream-checker

# Or run directly with uv for testing
uv run python -m xarray_upstream_checker.main
```

### Testing and Linting

```bash
# Run linting and formatting
uv run ruff check .
uv run ruff format .

# Install pre-commit hooks
uv run pre-commit install

# Test CLI without running
xarray-upstream-checker --help

# Test installation
uv tool uninstall xarray-upstream-checker
uv tool install -e .
xarray-upstream-checker
```

### Development Commands

```bash
# Quick test run during development
uv run python -m xarray_upstream_checker

# Check package structure
uv run python -c "from xarray_upstream_checker import main; print('Import works')"

# Reinstall after changes
uv tool install -e . --force-reinstall
```

## License

MIT License - see the LICENSE file for details.
