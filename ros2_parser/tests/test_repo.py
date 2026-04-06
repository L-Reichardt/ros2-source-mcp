"""Unit tests for RepoFetcher clone logic (tag → v-tag → branch fallback)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ros2_indexer.fetchers.repo import RepoFetcher
from ros2_indexer.models import RepoInfo


@pytest.fixture
def fetcher():
    return RepoFetcher()


def _make_repo_info(
    *,
    name: str = "test_repo",
    url: str = "https://github.com/org/test_repo.git",
    branch: str = "main",
    tag: str | None = None,
) -> RepoInfo:
    return RepoInfo(name=name, url=url, branch=branch, tag=tag)


def _mock_run_success(target: Path):
    """Return a side_effect that creates the target dir and succeeds."""

    def side_effect(*args, **kwargs):
        target.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    return side_effect


def _mock_run_fail():
    """Return a CompletedProcess that indicates clone failure."""
    return subprocess.CompletedProcess(["git", "clone"], 128, stdout="", stderr="fatal: not found")


# ---------------------------------------------------------------------------
# Tag fallback chain
# ---------------------------------------------------------------------------


@patch("ros2_indexer.fetchers.repo.REPOS_DIR")
@patch("subprocess.run")
def test_clone_uses_tag_first(mock_run, mock_repos_dir, tmp_path, fetcher):
    """When tag is set, clone attempts tag first."""
    mock_repos_dir.__truediv__ = lambda self, x: tmp_path / x
    mock_repos_dir.mkdir = MagicMock()
    target = tmp_path / "test_repo"

    mock_run.side_effect = _mock_run_success(target)
    info = _make_repo_info(tag="1.0.0")

    result = fetcher.clone(info)
    assert result == target
    # First call should use --branch=1.0.0
    first_call_args = mock_run.call_args_list[0][0][0]
    assert "--branch=1.0.0" in first_call_args


@patch("ros2_indexer.fetchers.repo.REPOS_DIR")
@patch("subprocess.run")
def test_clone_falls_back_to_v_prefix(mock_run, mock_repos_dir, tmp_path, fetcher):
    """When tag fails, try v-prefixed tag."""
    mock_repos_dir.__truediv__ = lambda self, x: tmp_path / x
    mock_repos_dir.mkdir = MagicMock()
    target = tmp_path / "test_repo"

    def side_effect(cmd, **kwargs):
        branch_arg = next(a for a in cmd if a.startswith("--branch="))
        if branch_arg == "--branch=1.0.0":
            return _mock_run_fail()
        # v1.0.0 succeeds
        target.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    info = _make_repo_info(tag="1.0.0")

    result = fetcher.clone(info)
    assert result == target
    assert mock_run.call_count == 2
    second_call_args = mock_run.call_args_list[1][0][0]
    assert "--branch=v1.0.0" in second_call_args


@patch("ros2_indexer.fetchers.repo.REPOS_DIR")
@patch("subprocess.run")
def test_clone_falls_back_to_branch(mock_run, mock_repos_dir, tmp_path, fetcher):
    """When tag and v-tag both fail, fall back to branch."""
    mock_repos_dir.__truediv__ = lambda self, x: tmp_path / x
    mock_repos_dir.mkdir = MagicMock()
    target = tmp_path / "test_repo"

    def side_effect(cmd, **kwargs):
        branch_arg = next(a for a in cmd if a.startswith("--branch="))
        if branch_arg in ("--branch=1.0.0", "--branch=v1.0.0"):
            return _mock_run_fail()
        # branch 'main' succeeds
        target.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    info = _make_repo_info(tag="1.0.0", branch="main")

    result = fetcher.clone(info)
    assert result == target
    assert mock_run.call_count == 3
    third_call_args = mock_run.call_args_list[2][0][0]
    assert "--branch=main" in third_call_args


@patch("ros2_indexer.fetchers.repo.REPOS_DIR")
@patch("subprocess.run")
def test_clone_all_refs_fail_raises(mock_run, mock_repos_dir, tmp_path, fetcher):
    """When all refs fail, raises CalledProcessError."""
    mock_repos_dir.__truediv__ = lambda self, x: tmp_path / x
    mock_repos_dir.mkdir = MagicMock()

    mock_run.return_value = _mock_run_fail()
    info = _make_repo_info(tag="1.0.0", branch="main")

    with pytest.raises(subprocess.CalledProcessError):
        fetcher.clone(info)
    # tag, v-tag, branch = 3 attempts
    assert mock_run.call_count == 3


@patch("ros2_indexer.fetchers.repo.REPOS_DIR")
@patch("subprocess.run")
def test_clone_no_tag_tries_branch_only(mock_run, mock_repos_dir, tmp_path, fetcher):
    """When no tag is set, only branch is tried."""
    mock_repos_dir.__truediv__ = lambda self, x: tmp_path / x
    mock_repos_dir.mkdir = MagicMock()
    target = tmp_path / "test_repo"

    mock_run.side_effect = _mock_run_success(target)
    info = _make_repo_info(tag=None, branch="jazzy")

    result = fetcher.clone(info)
    assert result == target
    assert mock_run.call_count == 1
    first_call_args = mock_run.call_args_list[0][0][0]
    assert "--branch=jazzy" in first_call_args


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------


def test_clone_rejects_invalid_repo_name(fetcher):
    info = _make_repo_info(name="../evil")
    with pytest.raises(ValueError, match="Invalid repo name"):
        fetcher.clone(info)


def test_clone_rejects_non_https_url(fetcher):
    info = _make_repo_info(url="git@github.com:org/repo.git")
    with pytest.raises(ValueError, match="Only https://"):
        fetcher.clone(info)


# ---------------------------------------------------------------------------
# Existing clone reuse
# ---------------------------------------------------------------------------


@patch("ros2_indexer.fetchers.repo.REPOS_DIR")
@patch("subprocess.run")
def test_clone_reuses_existing_dir(mock_run, mock_repos_dir, tmp_path, fetcher):
    """If the target dir already exists, skip cloning."""
    mock_repos_dir.__truediv__ = lambda self, x: tmp_path / x
    target = tmp_path / "test_repo"
    target.mkdir()

    info = _make_repo_info()
    result = fetcher.clone(info)
    assert result == target
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


@patch("ros2_indexer.fetchers.repo.REPOS_DIR")
@patch("subprocess.run")
def test_clone_passes_timeout(mock_run, mock_repos_dir, tmp_path, fetcher):
    """subprocess.run is called with timeout=120."""
    mock_repos_dir.__truediv__ = lambda self, x: tmp_path / x
    mock_repos_dir.mkdir = MagicMock()
    target = tmp_path / "test_repo"

    mock_run.side_effect = _mock_run_success(target)
    info = _make_repo_info()

    fetcher.clone(info)
    kwargs = mock_run.call_args_list[0][1]
    assert kwargs.get("timeout") == 120
