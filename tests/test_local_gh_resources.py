# SPDX-FileCopyrightText: GitHub, Inc.
# SPDX-License-Identifier: MIT

import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

import seclab_taskflows.mcp_servers.local_gh_resources as lgr_mod


ROOT = "owner-repo-abc1234"


def _make_zip(zip_path: Path, files: dict[str, str]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for path, content in files.items():
            zf.writestr(f"{ROOT}/{path}", content)


class TestSourceExtraction:
    def test_safe_extract_strips_github_zipball_root(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "owner" / "repo.zip"
            target_dir = lgr_mod._source_extract_path(tmp_dir)
            _make_zip(zip_path, {"src/main.py": "print('hello')\n", "README.md": "# Repo\n"})

            lgr_mod._safe_extract_source_zip(zip_path, target_dir)

            assert (target_dir / "src" / "main.py").read_text() == "print('hello')\n"
            assert (target_dir / "README.md").read_text() == "# Repo\n"
            assert not (target_dir / ROOT).exists()

    def test_safe_extract_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "owner" / "repo.zip"
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr(f"{ROOT}/../evil.py", "bad\n")

            with pytest.raises(RuntimeError, match="Invalid path"):
                lgr_mod._safe_extract_source_zip(zip_path, Path(tmp_dir) / "owner" / "repo")

    def test_safe_extract_replaces_existing_target_symlink(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "owner" / "repo.zip"
            target_dir = Path(tmp_dir) / "owner" / "repo"
            outside_dir = Path(tmp_dir) / "outside"
            outside_dir.mkdir()
            _make_zip(zip_path, {"main.py": "print('hello')\n"})
            target_dir.symlink_to(outside_dir, target_is_directory=True)

            lgr_mod._safe_extract_source_zip(zip_path, target_dir)

            assert not target_dir.is_symlink()
            assert (target_dir / "main.py").read_text() == "print('hello')\n"
            assert list(outside_dir.iterdir()) == []

    @pytest.mark.asyncio
    async def test_clear_local_repo_removes_archive_and_extracted_source(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            owner_dir = Path(tmp_dir) / "owner"
            source_zip = owner_dir / "repo.zip"
            extracted_dir = lgr_mod._source_extract_path(tmp_dir)
            _make_zip(source_zip, {"main.py": "print('hello')\n"})
            extracted_dir.mkdir(parents=True)
            (extracted_dir / "main.py").write_text("print('hello')\n")

            with patch.object(lgr_mod, "LOCAL_GH_DIR", os.path.realpath(tmp_dir)):
                result = await lgr_mod.clear_local_repo(owner="owner", repo="repo")

            assert result == "Cleared the locally stored owner/repo"
            assert not source_zip.exists()
            assert not extracted_dir.exists()

    def test_source_extract_path_is_fixed_for_repo_under_test(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            assert lgr_mod._source_extract_path(tmp_dir) == Path(tmp_dir) / "repo_under_test"