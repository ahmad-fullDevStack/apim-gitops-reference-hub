"""APIM-config CI checks.

Each module exposes a pure ``check(changed_files, repo_root, config)`` function
that returns a list of :class:`Violation`. The CLI shims in each module's
``__main__`` block are thin wrappers around that function so the scripts run
identically from a GitHub Actions workflow, an Azure Pipeline, or a developer's
shell.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
