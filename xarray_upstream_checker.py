#!/usr/bin/env -S uv run
"""
Zarr Upstream Compatibility Checker

This script checks the most recent upstream-dev CI workflow run for xarray
and reports on Zarr compatibility status and version information.

Usage:
    uv run zarr_upstream_checker.py

Requirements:
    - gh CLI must be installed and authenticated
"""

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "rich",
# ]
# ///

import json
import re
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markup import escape

console = Console()


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors"""

    pass


class ZarrUpstreamChecker:
    def __init__(self):
        self.xarray_repo = "pydata/xarray"
        self.zarr_repo = "zarr-developers/zarr-python"
        self.workflow_name = "upstream-dev-ci.yaml"

    def run_gh_command(self, args: List[str]) -> Dict:
        """Run a gh CLI command and return JSON response"""
        try:
            result = subprocess.run(
                ["gh"] + args, capture_output=True, text=True, check=True
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            if (
                "not found" in e.stderr.lower()
                or "command not found" in e.stderr.lower()
            ):
                raise GitHubAPIError(
                    "gh CLI not found. Please install GitHub CLI: https://cli.github.com/"
                )
            elif (
                "authentication" in e.stderr.lower()
                or "not logged in" in e.stderr.lower()
            ):
                raise GitHubAPIError(
                    "gh CLI not authenticated. Please run: gh auth login"
                )
            else:
                raise GitHubAPIError(f"gh CLI error: {e.stderr}")
        except json.JSONDecodeError:
            raise GitHubAPIError("Invalid JSON response from gh CLI")

    def get_latest_workflow_run_with_tests(self) -> Dict:
        """Get the most recent scheduled workflow run where upstream-dev tests actually executed"""
        try:
            # First, try to get scheduled runs only (these are most likely to have actual tests)
            scheduled_runs = self.run_gh_command(
                [
                    "run",
                    "list",
                    "--repo",
                    self.xarray_repo,
                    "--workflow",
                    self.workflow_name,
                    "--branch",
                    "main",
                    "--event",
                    "schedule",
                    "--limit",
                    "10",  # Scheduled runs are more likely to have tests
                    "--json",
                    "databaseId,number,headBranch,headSha,status,conclusion,createdAt,updatedAt,event",
                ]
            )

            if scheduled_runs:
                console.print(f"[green]Found {len(scheduled_runs)} scheduled runs to check[/green]")
                for i, run in enumerate(scheduled_runs):
                    console.print(f"[dim]Checking scheduled run {i+1}/{len(scheduled_runs)}: {run['databaseId']}[/dim]")

                    # Get jobs for this run
                    jobs = self.get_workflow_jobs(run["databaseId"])

                    # Find upstream-dev job
                    upstream_dev_job = next(
                        (job for job in jobs
                         if job.get("name", "").lower().startswith("upstream-dev")
                         and "detect" not in job.get("name", "").lower()
                         and "mypy" not in job.get("name", "").lower()),
                        None,
                    )

                    if upstream_dev_job:
                        conclusion = upstream_dev_job.get("conclusion")
                        console.print(f"[dim]  → upstream-dev job found with conclusion: {conclusion}[/dim]")

                        # Scheduled runs should have actual test execution
                        if conclusion in ["success", "failure"]:
                            console.print(f"[green]Found scheduled run with tests: {run['databaseId']}[/green]")
                            return run
                    else:
                        console.print(f"[dim]  → No upstream-dev job found[/dim]")

            # Fallback: if no scheduled runs with tests found, search all runs
            console.print("[yellow]No scheduled runs with tests found, searching all recent runs...[/yellow]")
            all_runs = self.run_gh_command(
                [
                    "run",
                    "list",
                    "--repo",
                    self.xarray_repo,
                    "--workflow",
                    self.workflow_name,
                    "--branch",
                    "main",
                    "--limit",
                    "20",
                    "--json",
                    "databaseId,number,headBranch,headSha,status,conclusion,createdAt,updatedAt,event",
                ]
            )

            if not all_runs:
                raise GitHubAPIError("No workflow runs found on main branch")

            for i, run in enumerate(all_runs):
                console.print(f"[dim]Checking run {i+1}/{len(all_runs)}: {run['databaseId']} ({run.get('event', 'unknown')} event)[/dim]")

                jobs = self.get_workflow_jobs(run["databaseId"])
                upstream_dev_job = next(
                    (job for job in jobs
                     if job.get("name", "").lower().startswith("upstream-dev")
                     and "detect" not in job.get("name", "").lower()
                     and "mypy" not in job.get("name", "").lower()),
                    None,
                )

                if upstream_dev_job and upstream_dev_job.get("conclusion") in ["success", "failure"]:
                    console.print(f"[green]Found run with actual tests: {run['databaseId']} ({run.get('event', 'unknown')} event)[/green]")
                    return run

            # If still no runs with actual tests found, return the most recent one
            console.print("[yellow]Warning: No runs found where upstream-dev tests actually executed. Using most recent run.[/yellow]")
            return all_runs[0]

        except Exception as e:
            raise GitHubAPIError(f"Failed to get workflow runs: {e}")

    def get_workflow_jobs(self, run_id: int) -> List[Dict]:
        """Get jobs for a specific workflow run"""
        try:
            jobs = self.run_gh_command(
                [
                    "run",
                    "view",
                    str(run_id),
                    "--repo",
                    self.xarray_repo,
                    "--json",
                    "jobs",
                ]
            )

            return jobs.get("jobs", [])
        except Exception as e:
            console.print(f"[yellow]Warning: Could not get job details: {e}[/yellow]")
            return []

    def get_workflow_logs_summary(self, run_id: int) -> Optional[str]:
        """Try to get workflow logs and extract zarr version info"""
        version_patterns = [
            r"zarr:\s*(\d+\.\d+\.\d+(?:\.dev\d+)?(?:\+g[a-f0-9]+[a-z]*)?)",  # zarr: 3.1.3.dev23+g62d1a6abc
            r"zarr[_-]?python?\s*[=:]\s*(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # zarr-python=2.18.3.dev0+g1234
            r"zarr\s*[=:]\s*(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # zarr=2.18.3
            r"zarr[_-]?python?\s+(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # zarr-python 2.18.3
            r"zarr\s+(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # zarr 2.18.3
            r"Installing.*zarr[_-]?python?.*?(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # Installing zarr-python-2.18.3
            r"(?:Successfully installed|Requirement already satisfied).*zarr[_-]?python?[^\d]*(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # pip install output
        ]

        try:
            # First, get the upstream-dev job ID
            jobs_result = subprocess.run(
                ["gh", "run", "view", str(run_id), "--repo", self.xarray_repo, "--json", "jobs"],
                capture_output=True,
                text=True,
                check=True,
            )

            jobs_data = json.loads(jobs_result.stdout)
            upstream_job = next(
                (job for job in jobs_data.get("jobs", [])
                 if job.get("name", "").lower().startswith("upstream-dev")
                 and "detect" not in job.get("name", "").lower()
                 and "mypy" not in job.get("name", "").lower()),
                None,
            )

            if not upstream_job:
                return None

            job_id = upstream_job["databaseId"]
            console.print(f"[dim]Getting logs for upstream-dev job {job_id} to find zarr version[/dim]")

            # Second, get the logs for that specific job using API
            result = subprocess.run(
                ["gh", "api", f"repos/{self.xarray_repo}/actions/jobs/{job_id}/logs"],
                capture_output=True,
                text=True,
                check=True,
            )

            for pattern in version_patterns:
                matches = re.findall(pattern, result.stdout, re.IGNORECASE)
                if matches:
                    console.print(f"[dim]Found zarr version matches: {matches}[/dim]")
                    return max(set(matches), key=matches.count)

        except subprocess.CalledProcessError:
            pass  # Logs might not be accessible without proper permissions
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not extract version from logs: {e}[/yellow]"
            )

        return None

    def get_test_failures(self, run_id: int) -> Dict[str, List[str]]:
        """Extract test failure information from workflow logs"""
        failure_patterns = [
            # Match FAILED lines from pytest output (after ANSI codes are stripped)
            r"FAILED\s+([^:]+::[^-]+)",  # Just capture the test name, extract error type separately
        ]

        error_extraction_patterns = [
            r"FAILED\s+[^-]+ - (\w+(?:Error|Exception)):",  # Explicit error type
            r"FAILED\s+[^-]+ - (assert)",  # Assert failures (treat as AssertionError)
        ]

        zarr_related_keywords = [
            "zarr", "chunk", "codec", "storage", "blosc", "zlib", "gzip",
            "compression", "array_api", "buffer"
        ]

        try:
            # First, get the upstream-dev job ID
            jobs_result = subprocess.run(
                ["gh", "run", "view", str(run_id), "--repo", self.xarray_repo, "--json", "jobs"],
                capture_output=True,
                text=True,
                check=True,
            )

            jobs_data = json.loads(jobs_result.stdout)
            upstream_job = next(
                (job for job in jobs_data.get("jobs", [])
                 if job.get("name", "").lower().startswith("upstream-dev")
                 and "detect" not in job.get("name", "").lower()
                 and "mypy" not in job.get("name", "").lower()),
                None,
            )

            if not upstream_job:
                console.print(f"[yellow]Could not find upstream-dev job in run {run_id}[/yellow]")
                return {"zarr_related": [], "other_failures": [], "total_failures": 0}

            job_id = upstream_job["databaseId"]
            console.print(f"[dim]Getting logs for upstream-dev job {job_id}[/dim]")

            # Second, get the logs for that specific job using API
            result = subprocess.run(
                ["gh", "api", f"repos/{self.xarray_repo}/actions/jobs/{job_id}/logs"],
                capture_output=True,
                text=True,
                check=True,
            )

            console.print(f"[dim]Analyzing {len(result.stdout)} characters of log data for test failures...[/dim]")

            # Strip ANSI color codes from logs for better parsing
            clean_logs = re.sub(r'\x1b\[[0-9;]*m|\[[0-9;]*m', '', result.stdout)

            # Extract test names from FAILED lines
            test_names = []
            for pattern in failure_patterns:
                matches = re.findall(pattern, clean_logs, re.IGNORECASE | re.MULTILINE)
                if matches:
                    console.print(f"[dim]Found {len(matches)} test failures[/dim]")
                test_names.extend(matches)

            # Extract error types separately
            error_types = set()
            for pattern in error_extraction_patterns:
                matches = re.findall(pattern, clean_logs, re.IGNORECASE | re.MULTILINE)
                error_types.update(matches)

            # Convert "assert" to "AssertionError" for consistency
            if "assert" in error_types:
                error_types.remove("assert")
                error_types.add("AssertionError")

            console.print(f"[dim]Found {len(test_names)} test failures and {len(error_types)} error types[/dim]")

            # Categorize failures
            zarr_related = []
            other_failures = []

            for test_name in test_names:
                # Check if it's zarr-related
                is_zarr_related = any(keyword in test_name.lower() for keyword in zarr_related_keywords)

                # Clean up test name (remove file path, keep just class::method)
                clean_test_name = test_name.split("::")[-2:] if "::" in test_name else [test_name]
                clean_test_name = "::".join(clean_test_name)

                # Create display format
                if error_types:
                    display_name = f"{clean_test_name} ({', '.join(sorted(error_types))})"
                else:
                    display_name = clean_test_name

                if is_zarr_related:
                    zarr_related.append(display_name)
                else:
                    other_failures.append(display_name)

            return {
                "zarr_related": zarr_related,
                "other_failures": other_failures,
                "error_types": list(error_types),
                "total_failures": len(test_names)
            }

        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]Warning: Could not access workflow logs (exit code {e.returncode})[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract test failures: {e}[/yellow]")

        return {"zarr_related": [], "other_failures": [], "total_failures": 0}

    def get_zarr_latest_commit(self) -> Optional[Dict]:
        """Get the latest commit from zarr-python main branch"""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{self.zarr_repo}/commits",
                    "--jq",
                    ".[0] | {sha: .sha, date: .commit.committer.date}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            return json.loads(result.stdout)
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not get zarr latest commit: {e}[/yellow]"
            )
            return None

    def check_upstream_compatibility(self) -> Dict:
        """Main method to check upstream compatibility"""
        with console.status("Searching for workflow run with actual tests..."):
            # Get latest workflow run where tests actually executed
            latest_run = self.get_latest_workflow_run_with_tests()

            # Get job details
            jobs = self.get_workflow_jobs(latest_run["databaseId"])

            # Find detect-ci-trigger and upstream-dev jobs
            detect_trigger_job = next(
                (job for job in jobs if "detect" in job.get("name", "").lower() and "trigger" in job.get("name", "").lower()),
                None,
            )

            upstream_dev_job = next(
                (job for job in jobs
                 if job.get("name", "").lower().startswith("upstream-dev")
                 and "detect" not in job.get("name", "").lower()
                 and "mypy" not in job.get("name", "").lower()),
                None,
            )

            # Try to get zarr version from logs
            zarr_version_from_logs = self.get_workflow_logs_summary(
                latest_run["databaseId"]
            )

            # Get test failure information if tests failed
            test_failures = {}
            if upstream_dev_job and upstream_dev_job.get("conclusion") == "failure":
                test_failures = self.get_test_failures(latest_run["databaseId"])

            # Get latest zarr commit
            zarr_latest_commit = self.get_zarr_latest_commit()

        return {
            "workflow_run": latest_run,
            "detect_trigger_job": detect_trigger_job,
            "upstream_dev_job": upstream_dev_job,
            "zarr_version_from_logs": zarr_version_from_logs,
            "test_failures": test_failures,
            "zarr_latest_commit": zarr_latest_commit,
        }

    def format_results(self, results: Dict) -> None:
        """Format and display results using rich"""
        run = results["workflow_run"]
        job = results["upstream_dev_job"]
        log_version = results["zarr_version_from_logs"]
        test_failures = results.get("test_failures", {})
        zarr_commit = results["zarr_latest_commit"]

        # Main status panel
        conclusion = run["conclusion"]
        status_color = (
            "green"
            if conclusion == "success"
            else "red"
            if conclusion == "failure"
            else "yellow"
        )
        status_text = Text(
            f"Workflow Status: {conclusion or run['status']}",
            style=f"bold {status_color}",
        )

        console.print(
            Panel(status_text, title="🔄 Most Recent Run With Tests", title_align="left")
        )

        # Workflow details table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        workflow_url = (
            f"https://github.com/{self.xarray_repo}/actions/runs/{run['databaseId']}"
        )

        table.add_row("Workflow ID", str(run["databaseId"]))
        table.add_row("Run Number", str(run["number"]))
        table.add_row("Branch", run["headBranch"])
        table.add_row("Commit", run["headSha"][:8])
        table.add_row("Event Type", run.get("event", "unknown"))
        table.add_row("Started", run["createdAt"])
        table.add_row("Completed", run["updatedAt"])
        table.add_row("URL", workflow_url)

        console.print(table)

        # Check if tests actually ran based on job status
        tests_actually_ran = False
        job_status_text = ""

        if not job:
            job_status_text = "❌ Upstream-dev job not found in this run"
            job_status_color = "red"
        elif job.get("conclusion") == "skipped" or job.get("status") == "skipped":
            job_status_text = "⏭️ Upstream-dev job was skipped (tests not triggered)"
            job_status_color = "yellow"
        elif job.get("conclusion") in ["success", "failure"] or job.get("status") == "completed":
            tests_actually_ran = True
            job_conclusion = job.get("conclusion", job.get("status"))
            if job_conclusion == "success":
                job_status_text = "✅ Upstream-dev job ran successfully"
                job_status_color = "green"
            elif job_conclusion == "failure":
                job_status_text = "❌ Upstream-dev job failed"
                job_status_color = "red"
            else:
                job_status_text = f"🔄 Upstream-dev job: {job_conclusion}"
                job_status_color = "yellow"
        else:
            job_status_text = f"🔄 Upstream-dev job status: {job.get('status', 'unknown')}"
            job_status_color = "yellow"

        job_status = Text(job_status_text, style=f"bold {job_status_color}")
        console.print(
            Panel(job_status, title="📋 Upstream-dev Job", title_align="left")
        )

        # Version info
        if log_version:
            version_text = Text(
                f"Zarr version tested: {log_version}", style="bold cyan"
            )
        else:
            version_text = Text("Zarr version: Not found in logs", style="bold yellow")

        console.print(Panel(version_text, title="📦 Version Info", title_align="left"))

        # Test failure details
        if test_failures and test_failures.get("total_failures", 0) > 0:
            self._display_test_failures(test_failures)
        elif job and job.get("conclusion") == "failure":
            # Show that there were failures but we couldn't parse them
            no_details_text = Text(
                "⚠️ Tests failed, but could not access logs to determine specific failures.\n"
                f"Check the workflow logs manually: {workflow_url}",
                style="bold yellow"
            )
            console.print(Panel(no_details_text, title="🧪 Test Failures", title_align="left"))

        # Check workflow freshness against zarr commits
        self._display_freshness_check(run, zarr_commit)

        # Summary
        if tests_actually_ran and job.get("conclusion") == "success":
            if log_version:
                summary = Text(
                    f"🎉 Upstream-dev tests ran successfully with Zarr {log_version}",
                    style="bold green",
                )
            else:
                summary = Text(
                    "✅ Upstream-dev tests ran successfully, but version info unclear",
                    style="bold yellow",
                )
        elif tests_actually_ran and job.get("conclusion") == "failure":
            summary = Text(
                "❌ Upstream-dev tests ran but failed",
                style="bold red",
            )
        elif not job:
            summary = Text(
                "❌ Upstream-dev job was not found in the most recent run with tests",
                style="bold red",
            )
        elif job.get("conclusion") == "skipped" or job.get("status") == "skipped":
            summary = Text(
                "⏭️ Upstream-dev tests were skipped (not triggered for this run)",
                style="bold yellow",
            )
        else:
            job_status = job.get("conclusion", job.get("status", "unknown"))
            summary = Text(
                f"🔄 Upstream-dev job status unclear: {job_status}",
                style="bold yellow",
            )

        console.print(Panel(summary, title="📊 Summary", title_align="left"))

    def _display_freshness_check(self, run: Dict, zarr_commit: Optional[Dict]) -> None:
        """Display freshness check comparing workflow time to latest zarr commit"""
        if not zarr_commit:
            return

        try:
            workflow_time = datetime.fromisoformat(
                run["createdAt"].replace("Z", "+00:00")
            )
            zarr_commit_time = datetime.fromisoformat(
                zarr_commit["date"].replace("Z", "+00:00")
            )

            commit_info = f"Latest zarr commit: {zarr_commit['sha'][:8]} ({zarr_commit['date']})\nWorkflow started: {run['createdAt']}"

            if zarr_commit_time > workflow_time:
                warning_text = Text(
                    f"⚠️  Warning: Zarr has newer commits since this workflow ran\n{commit_info}",
                    style="bold yellow",
                )
                console.print(
                    Panel(warning_text, title="⚠️  Outdated Check", title_align="left")
                )
            else:
                freshness_text = Text(
                    f"✅ Workflow is current with latest zarr commits\n{commit_info}",
                    style="bold green",
                )
                console.print(
                    Panel(
                        freshness_text, title="🕐 Freshness Check", title_align="left"
                    )
                )
        except Exception as e:
            console.print(f"[yellow]Could not compare timestamps: {e}[/yellow]")

    def _display_test_failures(self, test_failures: Dict) -> None:
        """Display test failure breakdown by category"""
        zarr_related = test_failures.get("zarr_related", [])
        other_failures = test_failures.get("other_failures", [])
        error_types = test_failures.get("error_types", [])
        total = test_failures.get("total_failures", 0)

        # Create failure summary table
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Category", style="cyan", width=20)
        table.add_column("Count", style="white", width=10)
        table.add_column("Tests", style="white")

        if zarr_related:
            zarr_tests = "\n".join(zarr_related[:3])  # Show first 3 tests
            if len(zarr_related) > 3:
                zarr_tests += f"\n... and {len(zarr_related) - 3} more"
            table.add_row("🔧 Zarr-related", str(len(zarr_related)), zarr_tests)

        if other_failures:
            other_tests = "\n".join(other_failures[:3])  # Show first 3 tests
            if len(other_failures) > 3:
                other_tests += f"\n... and {len(other_failures) - 3} more"
            table.add_row("📦 Other upstream", str(len(other_failures)), other_tests)

        # Add error types if found
        if error_types:
            error_list = ", ".join(error_types)
            table.add_row("⚠️ Error Types", str(len(error_types)), error_list)

        # Summary analysis
        if zarr_related and not other_failures:
            analysis = Text("🎯 All failures appear to be zarr-related", style="bold yellow")
        elif other_failures and not zarr_related:
            analysis = Text("📦 All failures appear to be from other upstream dependencies", style="bold blue")
        elif zarr_related and other_failures:
            analysis = Text("🔀 Mixed failures: both zarr and other upstream issues", style="bold orange")
        else:
            analysis = Text("❓ Could not categorize test failures", style="bold red")

        console.print(Panel(table, title=f"🧪 Test Failures ({total} total)", title_align="left"))
        console.print(Panel(analysis, title="📊 Failure Analysis", title_align="left"))


def main():
    """Check Zarr upstream compatibility in xarray CI"""
    checker = ZarrUpstreamChecker()

    try:
        results = checker.check_upstream_compatibility()
        checker.format_results(results)
    except GitHubAPIError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
