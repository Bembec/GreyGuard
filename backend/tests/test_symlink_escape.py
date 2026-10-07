"""A symbolic link inside the sandbox must never give access to files outside it."""

import os

import pytest

from backend.app import tool_gateway


@pytest.fixture
def sandbox_with_escape_links(tmp_path, monkeypatch):
    sandbox = (tmp_path / "sandbox").resolve()
    outside = (tmp_path / "outside").resolve()
    sandbox.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("must stay unreachable", encoding="utf-8")
    try:
        os.symlink(outside, sandbox / "escape_dir", target_is_directory=True)
        os.symlink(outside / "secret.txt", sandbox / "escape_file.txt")
    except (OSError, NotImplementedError):
        pytest.skip("Creating symbolic links needs Windows Developer Mode or administrator rights.")
    monkeypatch.setattr(tool_gateway, "sandbox_root", sandbox)
    return sandbox


@pytest.mark.parametrize("target", ["escape_file.txt", "escape_dir/secret.txt", "escape_dir"])
def test_symlinks_pointing_outside_the_sandbox_are_refused(sandbox_with_escape_links, target):
    with pytest.raises(tool_gateway.ToolGatewayError, match="sandbox"):
        tool_gateway.normalize_target(target)


def test_regular_files_inside_the_sandbox_still_work(sandbox_with_escape_links):
    (sandbox_with_escape_links / "notes.txt").write_text("allowed", encoding="utf-8")
    assert tool_gateway.normalize_target("notes.txt").name == "notes.txt"
