"""xarray-upstream-checker: Monitor xarray's upstream dependency CI tests for zarr compatibility."""

from .checker import ZarrUpstreamChecker
from .exceptions import GitHubAPIError
from .main import main

__version__ = "0.1.0"
__all__ = ["GitHubAPIError", "ZarrUpstreamChecker", "main"]
