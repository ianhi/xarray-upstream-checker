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

- Python 3.9+
- **Optional**: [GitHub CLI (`gh`)](https://cli.github.com/) for higher API rate limits

The tool automatically falls back to direct GitHub REST API if `gh` CLI is not available, but this has stricter rate limits (60 requests/hour for unauthenticated requests).

To set up GitHub CLI for better performance:

```bash
# Install gh CLI (if not already installed)
# macOS
brew install gh
# Or see: https://cli.github.com/

# Authenticate
gh auth login
```

## Usage

### Basic Usage

Simply run the tool:

```bash
xarray-upstream-checker
```

### API Selection

Control which GitHub API to use:

```bash
# Let the tool automatically choose (default: prefers gh CLI if available)
xarray-upstream-checker --api auto

# Force using GitHub CLI (requires authentication)
xarray-upstream-checker --api gh

# Force using direct REST API (rate limited but no auth required)
xarray-upstream-checker --api rest

# Use environment variable to set default
export XARRAY_UPSTREAM_API=rest
xarray-upstream-checker
```

The tool will automatically detect and use the best available option:
- ✅ **gh CLI** (preferred): Higher rate limits, requires `gh auth login`
- 🔄 **REST API** (fallback): Works without authentication, 60 requests/hour limit

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

The tool uses either GitHub CLI (`gh`) or direct REST API to:
- Query the xarray repository's workflow runs
- Filter for priority events (scheduled and workflow_dispatch) on the main branch
- Find the most recent run where upstream-dev tests actually executed (not skipped)
- Parse job logs to extract zarr version and test failure details
- Categorize failures based on test names and keywords

**API Selection Logic:**
1. If `--api gh` specified: Use GitHub CLI (fails if not authenticated)
2. If `--api rest` specified: Use direct REST API
3. If `--api auto` (default): Try GitHub CLI first, fallback to REST API if unavailable
4. Environment variable `XARRAY_UPSTREAM_API` can set the default preference

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

# Test different API modes
xarray-upstream-checker --api rest  # Test REST API fallback
xarray-upstream-checker --api gh    # Test GitHub CLI (requires auth)

# Test installation
uv tool uninstall xarray-upstream-checker
uv tool install -e .
xarray-upstream-checker
```

### Development Commands

```bash
# Quick test run during development
uv run python -m xarray_upstream_checker

# Test different API modes in development
uv run python -m xarray_upstream_checker --api rest
XARRAY_UPSTREAM_API=rest uv run python -m xarray_upstream_checker

# Check package structure
uv run python -c "from xarray_upstream_checker import main; print('Import works')"

# Reinstall after changes
uv tool install -e . --force-reinstall
```

## License

MIT License - see the LICENSE file for details.
