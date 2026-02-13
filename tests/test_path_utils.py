"""Tests for path normalization."""

from agent_sessions.path_utils import normalize_directory_path


def test_normalize_absolute():
    result = normalize_directory_path("/home/user/project")
    assert result == "/home/user/project"


def test_normalize_tilde():
    result = normalize_directory_path("~/project")
    assert "/project" in result
    assert "~" not in result


def test_normalize_relative():
    result = normalize_directory_path(".")
    assert result.startswith("/")
