"""Core ZarrUpstreamChecker class for analyzing xarray CI."""

import re
from typing import Optional

from rich.console import Console

from .exceptions import GitHubAPIError
from .github_api import GitHubAPIClient

console = Console()


class ZarrUpstreamChecker:
    def __init__(self, api_choice: Optional[str] = None):
        self.xarray_repo = "pydata/xarray"
        self.zarr_repo = "zarr-developers/zarr-python"
        self.workflow_name = "upstream-dev-ci.yaml"
        self.github_api = GitHubAPIClient(force_api=api_choice)

    def get_latest_workflow_run_with_tests(self) -> dict:
        """Get the most recent workflow run where upstream-dev tests actually executed"""
        try:
            # First, try to get scheduled and workflow_dispatch runs (most likely to have actual tests)
            priority_events = ["schedule", "workflow_dispatch"]
            priority_runs = []

            for event in priority_events:
                runs = self.github_api.get_workflow_runs(
                    repo=self.xarray_repo,
                    workflow=self.workflow_name,
                    event=event,
                    limit=5,
                )
                priority_runs.extend(runs)

            # Sort by creation time (most recent first)
            priority_runs.sort(key=lambda x: x["createdAt"], reverse=True)

            if priority_runs:
                console.print(
                    f"[green]Found {len(priority_runs)} priority runs (schedule/workflow_dispatch) to check[/green]"
                )
                for i, run in enumerate(priority_runs):
                    console.print(
                        f"[dim]Checking {run.get('event', 'unknown')} run {i + 1}/{len(priority_runs)}: {run['databaseId']}[/dim]"
                    )

                    # Get jobs for this run
                    jobs = self.get_workflow_jobs(run["databaseId"])

                    # Find upstream-dev job
                    upstream_dev_job = next(
                        (
                            job
                            for job in jobs
                            if job.get("name", "").lower().startswith("upstream-dev")
                            and "detect" not in job.get("name", "").lower()
                            and "mypy" not in job.get("name", "").lower()
                        ),
                        None,
                    )

                    if upstream_dev_job:
                        conclusion = upstream_dev_job.get("conclusion")
                        console.print(
                            f"[dim]  → upstream-dev job found with conclusion: {conclusion}[/dim]"
                        )

                        # Priority runs should have actual test execution
                        if conclusion in ["success", "failure"]:
                            console.print(
                                f"[green]Found {run.get('event', 'unknown')} run with tests: {run['databaseId']}[/green]"
                            )
                            return run
                    else:
                        console.print("[dim]  → No upstream-dev job found[/dim]")

            # Fallback: if no priority runs with tests found, search all runs
            console.print(
                "[yellow]No priority runs with tests found, searching all recent runs...[/yellow]"
            )
            all_runs = self.github_api.get_workflow_runs(
                repo=self.xarray_repo,
                workflow=self.workflow_name,
                branch="main",
                limit=20,
            )

            if not all_runs:
                raise GitHubAPIError("No workflow runs found on main branch")

            for i, run in enumerate(all_runs):
                console.print(
                    f"[dim]Checking run {i + 1}/{len(all_runs)}: {run['databaseId']} ({run.get('event', 'unknown')} event)[/dim]"
                )

                jobs = self.get_workflow_jobs(run["databaseId"])
                upstream_dev_job = next(
                    (
                        job
                        for job in jobs
                        if job.get("name", "").lower().startswith("upstream-dev")
                        and "detect" not in job.get("name", "").lower()
                        and "mypy" not in job.get("name", "").lower()
                    ),
                    None,
                )

                if upstream_dev_job and upstream_dev_job.get("conclusion") in [
                    "success",
                    "failure",
                ]:
                    console.print(
                        f"[green]Found run with actual tests: {run['databaseId']} ({run.get('event', 'unknown')} event)[/green]"
                    )
                    return run

            # If still no runs with actual tests found, return the most recent one
            console.print(
                "[yellow]Warning: No runs found where upstream-dev tests actually executed. Using most recent run.[/yellow]"
            )
            return all_runs[0]

        except Exception as e:
            raise GitHubAPIError(f"Failed to get workflow runs: {e}") from e

    def get_workflow_jobs(self, run_id: int) -> list[dict]:
        """Get jobs for a specific workflow run"""
        try:
            return self.github_api.get_workflow_jobs(self.xarray_repo, run_id)
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not get jobs for run {run_id}: {e}[/yellow]"
            )
            return []

    def _find_upstream_dev_job(self, run_id: int) -> Optional[dict]:
        """Find the upstream-dev job for a given workflow run."""
        try:
            jobs = self.github_api.get_workflow_jobs(self.xarray_repo, run_id)
            return next(
                (
                    job
                    for job in jobs
                    if job.get("name", "").lower().startswith("upstream-dev")
                    and "detect" not in job.get("name", "").lower()
                    and "mypy" not in job.get("name", "").lower()
                ),
                None,
            )
        except Exception:
            return None

    def get_workflow_logs_summary(self, run_id: int) -> Optional[str]:
        """Extract zarr version from workflow logs"""
        version_patterns = [
            r"zarr:\s+(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # zarr: 3.1.3.dev23+g62d1a6abc
            r"zarr\s+(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # zarr 2.18.3
            r"Installing.*zarr[_-]?python?.*?(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # Installing zarr-python-2.18.3
            r"(?:Successfully installed|Requirement already satisfied).*zarr[_-]?python?[^\d]*(\d+\.\d+\.\d+(?:[\.\w\d\-\+]+)?)",  # pip install output
        ]

        try:
            upstream_job = self._find_upstream_dev_job(run_id)
            if not upstream_job:
                return None

            job_id = upstream_job.get("databaseId") or upstream_job.get("id")
            console.print(
                f"[dim]Getting logs for upstream-dev job {job_id} to find zarr version[/dim]"
            )

            log_content = self.github_api.get_job_logs(self.xarray_repo, job_id)

            for pattern in version_patterns:
                matches = re.findall(pattern, log_content, re.IGNORECASE)
                if matches:
                    console.print(f"[dim]Found zarr version matches: {matches}[/dim]")
                    return matches[0]

            return None

        except Exception as e:
            console.print(f"[dim]Could not extract zarr version from logs: {e}[/dim]")
            return None

    def get_test_failures(self, run_id: int) -> dict[str, list[str]]:
        """Extract test failure information from workflow logs"""
        failure_patterns = [
            r"FAILED\s+([^:]+::[^-]+)",  # FAILED test_module.py::TestClass::test_method
        ]

        error_extraction_patterns = [
            r"FAILED\s+[^-]+ - (\w+(?:Error|Exception)):",  # Explicit error type
            r"FAILED\s+[^-]+ - (assert)",  # Assert failures (treat as AssertionError)
        ]

        zarr_related_keywords = [
            "zarr",
            "chunk",
            "codec",
            "storage",
            "blosc",
            "zlib",
            "gzip",
            "compression",
            "array_api",
            "buffer",
        ]

        try:
            upstream_job = self._find_upstream_dev_job(run_id)
            if not upstream_job:
                console.print(
                    f"[yellow]Could not find upstream-dev job in run {run_id}[/yellow]"
                )
                return {"zarr_related": [], "other_failures": [], "total_failures": 0}

            job_id = upstream_job.get("databaseId") or upstream_job.get("id")
            console.print(f"[dim]Getting logs for upstream-dev job {job_id}[/dim]")

            log_content = self.github_api.get_job_logs(self.xarray_repo, job_id)

            console.print(
                f"[dim]Analyzing {len(log_content)} characters of log data for test failures...[/dim]"
            )

            # Strip ANSI color codes from logs for better parsing
            clean_logs = re.sub(r"\x1b\[[0-9;]*m|\[[0-9;]*m", "", log_content)

            # Extract test names from FAILED lines
            test_names = []
            for pattern in failure_patterns:
                matches = re.findall(pattern, clean_logs, re.IGNORECASE | re.MULTILINE)
                if matches:
                    console.print(f"[dim]Found {len(matches)} test failures[/dim]")
                test_names.extend(matches)

            # Extract error types
            error_types = set()
            for pattern in error_extraction_patterns:
                matches = re.findall(pattern, clean_logs, re.IGNORECASE | re.MULTILINE)
                error_types.update(matches)

            # Convert "assert" to "AssertionError" for consistency
            if "assert" in error_types:
                error_types.remove("assert")
                error_types.add("AssertionError")

            console.print(
                f"[dim]Found {len(test_names)} test failures and {len(error_types)} error types[/dim]"
            )

            # Categorize failures
            zarr_related = []
            other_failures = []

            for test_name in test_names:
                # Check if it's zarr-related
                is_zarr_related = any(
                    keyword in test_name.lower() for keyword in zarr_related_keywords
                )

                # Clean up test name (remove file path, keep just class::method)
                clean_test_name = (
                    test_name.split("::")[-2:] if "::" in test_name else [test_name]
                )
                clean_test_name = "::".join(clean_test_name)

                # Create display format
                if error_types:
                    display_name = (
                        f"{clean_test_name} ({', '.join(sorted(error_types))})"
                    )
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
                "total_failures": len(test_names),
            }

        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not extract test failures: {e}[/yellow]"
            )

        return {"zarr_related": [], "other_failures": [], "total_failures": 0}

    def get_zarr_latest_commit(self) -> Optional[dict]:
        """Get the latest commit from zarr-python main branch"""
        return self.github_api.get_latest_commit(self.zarr_repo)

    def check_upstream_compatibility(self) -> dict:
        """Main method to check xarray upstream compatibility with zarr"""
        # Get latest workflow run where tests actually executed
        latest_run = self.get_latest_workflow_run_with_tests()

        # Get job details
        jobs = self.get_workflow_jobs(latest_run["databaseId"])

        # Find detect-ci-trigger and upstream-dev jobs
        detect_trigger_job = next(
            (
                job
                for job in jobs
                if "detect" in job.get("name", "").lower()
                and "trigger" in job.get("name", "").lower()
            ),
            None,
        )

        upstream_dev_job = next(
            (
                job
                for job in jobs
                if job.get("name", "").lower().startswith("upstream-dev")
                and "detect" not in job.get("name", "").lower()
                and "mypy" not in job.get("name", "").lower()
            ),
            None,
        )

        # Try to get zarr version from logs
        zarr_version_from_logs = self.get_workflow_logs_summary(
            latest_run["databaseId"]
        )

        # Get test failure details if job failed
        test_failures = {}
        if upstream_dev_job and upstream_dev_job.get("conclusion") == "failure":
            test_failures = self.get_test_failures(latest_run["databaseId"])

        # Get latest zarr commit for freshness check
        zarr_commit = self.get_zarr_latest_commit()

        return {
            "run": latest_run,
            "detect_trigger_job": detect_trigger_job,
            "upstream_dev_job": upstream_dev_job,
            "zarr_version_from_logs": zarr_version_from_logs,
            "test_failures": test_failures,
            "zarr_commit": zarr_commit,
        }
