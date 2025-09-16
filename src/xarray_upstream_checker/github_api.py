"""GitHub API client with fallback from gh CLI to direct HTTP requests."""

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional
from typing import Union

from rich.console import Console

from .exceptions import GitHubAPIError

console = Console()


class GitHubAPIClient:
    """GitHub API client that falls back from gh CLI to direct HTTP requests."""

    def __init__(self, force_api: Optional[str] = None):
        self.base_url = "https://api.github.com"

        # Check environment variable or use parameter
        if force_api and force_api != "auto":
            api_preference = force_api
        else:
            api_preference = os.getenv("XARRAY_UPSTREAM_API", force_api or "auto")

        if api_preference == "rest":
            self.use_gh_cli = False
            console.print("[blue]Using direct GitHub REST API (as requested)[/blue]")
        elif api_preference == "gh":
            if self._detect_gh_cli_availability():
                self.use_gh_cli = True
                console.print("[green]Using gh CLI (as requested)[/green]")
            else:
                console.print(
                    "[yellow]gh CLI requested but not available, falling back to REST API[/yellow]"
                )
                self.use_gh_cli = False
        else:  # auto
            self.use_gh_cli = self._detect_gh_cli_availability()
            if not self.use_gh_cli:
                console.print(
                    "[yellow]gh CLI not available, using direct GitHub API (rate limited)[/yellow]"
                )

    def _detect_gh_cli_availability(self) -> bool:
        """Check if gh CLI is available and authenticated."""
        try:
            # Check if gh command exists
            subprocess.run(
                ["gh", "--version"], capture_output=True, text=True, check=True
            )

            # Check if authenticated
            auth_result = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True
            )

            if auth_result.returncode == 0:
                console.print("[green]Using gh CLI (authenticated)[/green]")
                return True
            else:
                console.print(
                    "[yellow]gh CLI found but not authenticated, using direct API[/yellow]"
                )
                return False

        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _make_http_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Union[dict, list]:
        """Make a direct HTTP request to GitHub API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "xarray-upstream-checker/0.1.0",
        }

        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    return json.loads(response.read().decode())
                else:
                    raise GitHubAPIError(
                        f"GitHub API returned status {response.status}"
                    )

        except urllib.error.HTTPError as e:
            if e.code == 403:
                # Likely rate limiting
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded. Try again later or install/authenticate gh CLI for higher limits."
                ) from e
            elif e.code == 404:
                raise GitHubAPIError("Repository or resource not found") from e
            else:
                raise GitHubAPIError(f"GitHub API error: {e.code} {e.reason}") from e
        except urllib.error.URLError as e:
            raise GitHubAPIError(
                f"Network error accessing GitHub API: {e.reason}"
            ) from e
        except json.JSONDecodeError as e:
            raise GitHubAPIError("Invalid JSON response from GitHub API") from e

    def _make_gh_cli_request(self, args: list[str]) -> Union[dict, list]:
        """Make a request using gh CLI."""
        try:
            result = subprocess.run(
                ["gh", *args], capture_output=True, text=True, check=True
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            if (
                "authentication" in e.stderr.lower()
                or "not logged in" in e.stderr.lower()
            ):
                raise GitHubAPIError(
                    "gh CLI not authenticated. Please run: gh auth login"
                ) from None
            else:
                raise GitHubAPIError(f"gh CLI error: {e.stderr}") from e
        except json.JSONDecodeError:
            raise GitHubAPIError("Invalid JSON response from gh CLI") from None

    def get_workflow_runs(
        self,
        repo: str,
        workflow: str,
        event: Optional[str] = None,
        branch: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get workflow runs for a repository."""
        if self.use_gh_cli:
            args = [
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                workflow,
                "--limit",
                str(limit),
                "--json",
                "databaseId,number,headBranch,headSha,status,conclusion,createdAt,updatedAt,event",
            ]
            if event:
                args.extend(["--event", event])
            if branch:
                args.extend(["--branch", branch])

            return self._make_gh_cli_request(args)
        else:
            # Direct API call
            params = {
                "per_page": limit,
            }
            if event:
                params["event"] = event
            if branch:
                params["branch"] = branch

            response = self._make_http_request(f"repos/{repo}/actions/runs", params)

            # Transform API response to match gh CLI format
            runs = []
            for run in response.get("workflow_runs", []):
                if workflow in run.get("path", ""):  # Filter by workflow file
                    runs.append(
                        {
                            "databaseId": run["id"],
                            "number": run["run_number"],
                            "headBranch": run["head_branch"],
                            "headSha": run["head_sha"],
                            "status": run["status"],
                            "conclusion": run["conclusion"],
                            "createdAt": run["created_at"],
                            "updatedAt": run["updated_at"],
                            "event": run["event"],
                        }
                    )

            return runs

    def get_workflow_jobs(self, repo: str, run_id: int) -> list[dict]:
        """Get jobs for a specific workflow run."""
        if self.use_gh_cli:
            args = ["run", "view", str(run_id), "--repo", repo, "--json", "jobs"]
            result = self._make_gh_cli_request(args)
            return result.get("jobs", [])
        else:
            response = self._make_http_request(
                f"repos/{repo}/actions/runs/{run_id}/jobs"
            )
            return response.get("jobs", [])

    def get_job_logs(self, repo: str, job_id: int) -> str:
        """Get logs for a specific job."""
        if self.use_gh_cli:
            # Use the API endpoint directly even with gh CLI
            result = subprocess.run(
                ["gh", "api", f"repos/{repo}/actions/jobs/{job_id}/logs"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        else:
            # Direct API call - this endpoint returns a redirect to log URL
            try:
                request = urllib.request.Request(
                    f"{self.base_url}/repos/{repo}/actions/jobs/{job_id}/logs"
                )
                request.add_header("Accept", "application/vnd.github.v3+json")
                request.add_header("User-Agent", "xarray-upstream-checker/0.1.0")

                with urllib.request.urlopen(request) as response:
                    return response.read().decode()

            except urllib.error.HTTPError as e:
                if e.code == 403:
                    raise GitHubAPIError(
                        "Cannot access job logs: GitHub API rate limit exceeded"
                    ) from e
                else:
                    raise GitHubAPIError(
                        f"Cannot access job logs: {e.code} {e.reason}"
                    ) from e

    def get_latest_commit(self, repo: str, branch: str = "main") -> Optional[dict]:
        """Get latest commit from a repository branch."""
        if self.use_gh_cli:
            try:
                result = subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{repo}/commits",
                        "--jq",
                        ".[0] | {sha: .sha, date: .commit.author.date}",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return json.loads(result.stdout)
            except Exception:
                return None
        else:
            try:
                response = self._make_http_request(
                    f"repos/{repo}/commits", {"sha": branch, "per_page": 1}
                )
                if response and len(response) > 0:
                    commit = response[0]
                    return {
                        "sha": commit["sha"],
                        "date": commit["commit"]["author"]["date"],
                    }
                return None
            except Exception:
                return None
