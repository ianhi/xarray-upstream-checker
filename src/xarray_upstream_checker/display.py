"""Rich display formatting for xarray upstream checker results."""

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def display_results(
    run: dict,
    detect_trigger_job: Optional[dict],
    upstream_dev_job: Optional[dict],
    zarr_version_from_logs: Optional[str],
    test_failures: dict,
    zarr_commit: Optional[dict],
) -> None:
    """Display comprehensive results using Rich formatting"""
    tests_actually_ran = False
    conclusion = run.get("conclusion") or run.get("status")

    # Main status panel
    status_color = (
        "green"
        if conclusion == "success"
        else "red"
        if conclusion in ["failure", "failed"]
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

    workflow_url = f"https://github.com/pydata/xarray/actions/runs/{run['databaseId']}"
    table.add_row("Workflow ID", str(run["databaseId"]))
    table.add_row("Run Number", str(run.get("number", "N/A")))
    table.add_row("Branch", run.get("headBranch", "N/A"))
    table.add_row("Commit", run.get("headSha", "N/A")[:8])
    table.add_row("Event Type", run.get("event", "N/A"))
    table.add_row("Started", run.get("createdAt", "N/A"))
    table.add_row("Completed", run.get("updatedAt", "N/A"))
    table.add_row("URL", workflow_url)

    console.print(table)

    # Job status analysis
    job = upstream_dev_job
    job_status_text = ""

    if not job:
        job_status_text = "❌ Upstream-dev job not found in this run"
        job_status_color = "red"
    elif job.get("conclusion") == "skipped" or job.get("status") == "skipped":
        job_status_text = "⏭️ Upstream-dev job was skipped (tests not triggered)"
        job_status_color = "yellow"
    elif (
        job.get("conclusion") in ["success", "failure"]
        or job.get("status") == "completed"
    ):
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
    console.print(Panel(job_status, title="📋 Upstream-dev Job", title_align="left"))

    # Version info
    if zarr_version_from_logs:
        version_text = Text(
            f"Zarr version tested: {zarr_version_from_logs}", style="bold green"
        )
        console.print(Panel(version_text, title="📦 Version Info", title_align="left"))

    # Test failure details
    if test_failures and test_failures.get("total_failures", 0) > 0:
        display_test_failures(test_failures)
    elif job and job.get("conclusion") == "failure":
        # Show that there were failures but we couldn't parse them
        no_details_text = Text(
            "⚠️ Tests failed, but could not access logs to determine specific failures.\n"
            f"Check the workflow logs manually: {workflow_url}",
            style="bold yellow",
        )
        console.print(
            Panel(no_details_text, title="🧪 Test Failures", title_align="left")
        )

    # Check workflow freshness against zarr commits
    display_freshness_check(run, zarr_commit)

    # Summary
    if tests_actually_ran and job.get("conclusion") == "success":
        if zarr_version_from_logs:
            summary = Text(
                f"✅ All upstream-dev tests passed with zarr {zarr_version_from_logs}",
                style="bold green",
            )
        else:
            summary = Text(
                "✅ All upstream-dev tests passed (zarr version not detected)",
                style="bold green",
            )
    elif tests_actually_ran and job.get("conclusion") == "failure":
        summary = Text("❌ Upstream-dev tests ran but failed", style="bold red")
    elif not tests_actually_ran:
        summary = Text(
            "⏭️ Upstream-dev tests were skipped (likely no changes detected)",
            style="bold yellow",
        )
    else:
        summary = Text("❓ Unable to determine test status", style="bold yellow")

    console.print(Panel(summary, title="📊 Summary", title_align="left"))


def display_freshness_check(run: dict, zarr_commit: Optional[dict]) -> None:
    """Display freshness check comparing workflow time to latest zarr commit"""
    if not zarr_commit:
        return

    try:
        workflow_time = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
        zarr_commit_time = datetime.fromisoformat(
            zarr_commit["date"].replace("Z", "+00:00")
        )

        # Check if workflow is testing recent zarr changes
        time_diff = workflow_time - zarr_commit_time
        hours_diff = abs(time_diff.total_seconds()) / 3600

        if hours_diff <= 24 and workflow_time >= zarr_commit_time:
            freshness_text = Text(
                "✅ Workflow is current with latest zarr commits", style="bold green"
            )
        elif hours_diff <= 72:
            freshness_text = Text(
                f"⚠️ Workflow may be slightly outdated ({hours_diff:.1f} hours behind zarr)",
                style="bold yellow",
            )
        else:
            freshness_text = Text(
                f"❌ Workflow appears outdated ({hours_diff/24:.1f} days behind zarr)",
                style="bold red",
            )

        freshness_text.append(
            f"\nLatest zarr commit: {zarr_commit['sha'][:8]} ({zarr_commit['date']})"
        )
        freshness_text.append(f"\nWorkflow started: {run['createdAt']}")

    except Exception:
        freshness_text = Text(
            "❓ Could not determine workflow freshness", style="bold yellow"
        )

    console.print(Panel(freshness_text, title="🕐 Freshness Check", title_align="left"))


def display_test_failures(test_failures: dict) -> None:
    """Display test failure details in a formatted table"""
    zarr_related = test_failures.get("zarr_related", [])
    other_failures = test_failures.get("other_failures", [])
    error_types = test_failures.get("error_types", [])
    total = test_failures.get("total_failures", 0)

    # Create table for test failures
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="white", justify="center")
    table.add_column("Tests", style="white")

    # Add zarr-related failures
    if zarr_related:
        zarr_list = "\n".join(zarr_related[:3])  # Show first 3
        if len(zarr_related) > 3:
            zarr_list += f"\n... and {len(zarr_related) - 3} more"
        table.add_row("🔧 Zarr-related", str(len(zarr_related)), zarr_list)

    # Add other upstream failures
    if other_failures:
        other_list = "\n".join(other_failures[:3])  # Show first 3
        if len(other_failures) > 3:
            other_list += f"\n... and {len(other_failures) - 3} more"
        table.add_row("📦 Other upstream", str(len(other_failures)), other_list)

    # Add error types if found
    if error_types:
        error_list = ", ".join(error_types)
        table.add_row("⚠️ Error Types", str(len(error_types)), error_list)

    # Summary analysis
    if zarr_related and not other_failures:
        analysis = Text(
            "🎯 All failures appear to be zarr-related", style="bold yellow"
        )
    elif other_failures and not zarr_related:
        analysis = Text(
            "📦 All failures appear to be from other upstream dependencies",
            style="bold blue",
        )
    elif zarr_related and other_failures:
        analysis = Text(
            "🔀 Mixed failures: both zarr and other upstream issues",
            style="bold orange",
        )
    else:
        analysis = Text("❓ Could not categorize test failures", style="bold red")

    console.print(
        Panel(table, title=f"🧪 Test Failures ({total} total)", title_align="left")
    )
    console.print(Panel(analysis, title="📊 Failure Analysis", title_align="left"))
