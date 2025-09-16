# Claude Code Project Instructions

## Project Overview

This is a Python CLI tool (`xarray-upstream-checker`) that monitors xarray's upstream dependency CI tests for zarr compatibility. It analyzes GitHub Actions workflow runs to determine if zarr changes are breaking xarray's tests.

**Core Purpose**: Find the most recent xarray CI run where upstream-dev tests actually executed (not skipped), analyze test failures, categorize them as zarr-related vs other upstream dependencies, and display results with rich formatting.

## Critical Implementation Details

### GitHub API Integration
- Uses `gh` CLI exclusively (not GitHub API directly)
- **Key Command**: `gh api repos/pydata/xarray/actions/jobs/{job_id}/logs` to get logs (NOT `gh run view --log`)
- Searches for **scheduled** runs first (most likely to have tests) then fallback to all runs
- Filters jobs with `job.get("name", "").lower().startswith("upstream-dev")` AND excludes "detect" and "mypy"
- Only considers jobs with conclusion in `["success", "failure"]` (not "skipped")

### Test Failure Analysis
- Strips ANSI codes with `re.sub(r'\x1b\[[0-9;]*m|\[[0-9;]*m', '', result.stdout)`
- Extracts test names with pattern: `r"FAILED\s+([^:]+::[^-]+)"`
- Categorizes as zarr-related using keywords: `["zarr", "chunk", "codec", "storage", "blosc", "zlib", "gzip", "compression", "array_api", "buffer"]`
- Extracts zarr version with pattern: `r"zarr:\s+(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)"`

### Module Structure
```
src/xarray_upstream_checker/
├── __init__.py         # Package exports: main, ZarrUpstreamChecker, GitHubAPIError
├── main.py            # CLI entry point with argparse (fixes --help issue)
├── checker.py         # Core logic: ZarrUpstreamChecker class
├── display.py         # Rich formatting: display_results, display_test_failures, etc.
└── exceptions.py      # GitHubAPIError exception
```

### Build System
- **Build backend**: `setuptools` (NOT hatchling - better for editable installs)
- **Package discovery**: `[tool.setuptools.packages.find] where = ["src"]`
- **Entry point**: `xarray-upstream-checker = "xarray_upstream_checker:main"`

## Development Commands

### Essential Commands
```bash
# Install for development
uv tool install -e .

# Test CLI without running
xarray-upstream-checker --help

# Run the tool
xarray-upstream-checker

# Linting (ALWAYS run before commits)
uv run ruff check .
uv run ruff format .
```

### Git Workflow
```bash
# ALWAYS be specific with git add
git add src/xarray_upstream_checker/main.py
git add pyproject.toml

# NEVER use git add .
# Pre-commit hooks will auto-format and may conflict
```

## Common Issues & Solutions

### Module Import Errors
- **Problem**: `ModuleNotFoundError: No module named 'xarray_upstream_checker'`
- **Solution**: Use setuptools build backend, ensure `packages = ["src"]` in pyproject.toml

### CLI Help Running Script
- **Problem**: `--help` flag executed main script logic
- **Solution**: Add `parser.parse_args()` before any script logic, handle in main()

### Log Access Issues
- **Problem**: Getting 0 characters from logs
- **Solution**: Use `gh api repos/{repo}/actions/jobs/{job_id}/logs` not `gh run view --log`

### Wrong Workflow Runs
- **Problem**: Finding runs where tests were skipped
- **Solution**: Check `conclusion in ["success", "failure"]` AND search scheduled runs first

## Code Patterns

### Error Handling
```python
try:
    # operation
except subprocess.CalledProcessError as e:
    if "not found" in e.stderr.lower():
        raise GitHubAPIError("gh CLI not found...") from None
    else:
        raise GitHubAPIError(f"gh CLI error: {e.stderr}") from e
```

### Rich Display
```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
console.print(Panel(text, title="Title", title_align="left"))
```

### Job Filtering
```python
upstream_job = next(
    (
        job
        for job in jobs
        if job.get("name", "").lower().startswith("upstream-dev")
        and "detect" not in job.get("name", "").lower()
        and "mypy" not in job.get("name", "").lower()
    ),
    None,
)
```

## Dependencies
- `rich>=10.0.0` - Terminal formatting (REQUIRED)
- `setuptools>=61.0` - Build backend
- External: GitHub CLI (`gh`) must be installed and authenticated

## Testing
- Test CLI help: `xarray-upstream-checker --help` (should NOT run script)
- Test execution: `xarray-upstream-checker` (should analyze CI and display results)
- Test editable install: `uv tool uninstall xarray-upstream-checker && uv tool install -e .`
