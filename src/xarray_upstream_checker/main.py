#!/usr/bin/env -S uv run
"""
Zarr Upstream Compatibility Checker

This script checks the most recent upstream-dev CI workflow run for xarray
and reports on Zarr compatibility status and version information.

Usage:
    xarray-upstream-checker

Requirements:
    - gh CLI must be installed and authenticated
"""

import argparse
import sys

from rich.console import Console

from .checker import ZarrUpstreamChecker
from .display import display_results
from .exceptions import GitHubAPIError

console = Console()


def main():
    """Check Zarr upstream compatibility in xarray CI"""
    parser = argparse.ArgumentParser(
        description="Monitor xarray's upstream dependency CI tests for zarr compatibility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  xarray-upstream-checker           # Check latest upstream-dev CI results
  xarray-upstream-checker --help    # Show this help message

This tool checks the most recent xarray upstream-dev CI workflow run
and reports on Zarr compatibility status, version information, and
test failure analysis.

Requirements:
  - gh CLI must be installed and authenticated
  - Internet connection to access GitHub API
        """.strip(),
    )

    parser.add_argument(
        "--version", action="version", version="xarray-upstream-checker 0.1.0"
    )

    parser.parse_args()

    checker = ZarrUpstreamChecker()

    try:
        results = checker.check_upstream_compatibility()
        display_results(
            results["run"],
            results["detect_trigger_job"],
            results["upstream_dev_job"],
            results["zarr_version_from_logs"],
            results["test_failures"],
            results["zarr_commit"],
        )
    except GitHubAPIError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
