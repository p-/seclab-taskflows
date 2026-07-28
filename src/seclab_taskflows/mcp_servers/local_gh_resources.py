# SPDX-FileCopyrightText: GitHub, Inc.
# SPDX-License-Identifier: MIT

import logging
from fastmcp import FastMCP
from pydantic import Field
import httpx
import json
import os
from pathlib import Path
import shutil
import aiofiles
import zipfile
from seclab_taskflow_agent.path_utils import mcp_data_dir, log_file_name

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename=log_file_name("mcp_local_gh_resources.log"),
    filemode="a",
)

mcp = FastMCP("LocalGHResources")

GH_TOKEN = os.getenv("GH_TOKEN")

LOCAL_GH_DIR = mcp_data_dir("seclab-taskflows", "local_gh_resources", "LOCAL_GH_DIR")
SOURCE_WORKSPACE_DIR = "repo_under_test"


def is_subdirectory(directory, potential_subdirectory):
    directory_path = Path(directory)
    potential_subdirectory_path = Path(potential_subdirectory)
    try:
        potential_subdirectory_path.relative_to(directory_path)
        return True
    except ValueError:
        return False


def sanitize_file_path(file_path, allow_paths):
    file_path = os.path.realpath(file_path)
    for allowed_path in allow_paths:
        if is_subdirectory(allowed_path, file_path):
            return Path(file_path)
    return None


def _source_archive_path(owner: str, repo: str, tmp_dir) -> Path:
    return Path(tmp_dir) / owner / f"{repo}.zip"


def _source_extract_path(tmp_dir) -> Path:
    return Path(tmp_dir) / SOURCE_WORKSPACE_DIR


def _safe_extract_source_zip(source_path: Path, target_dir: Path) -> None:
    """Extract a GitHub zipball into a stable repo directory without its root prefix."""
    if target_dir.exists() or target_dir.is_symlink():
        if target_dir.is_symlink() or not target_dir.is_dir():
            target_dir.unlink()
        else:
            shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_dir = target_dir.resolve()

    with zipfile.ZipFile(source_path) as z:
        for entry in z.infolist():
            if entry.is_dir():
                continue
            entry_path = Path(entry.filename)
            relative_parts = entry_path.parts[1:] if len(entry_path.parts) > 1 else entry_path.parts
            if not relative_parts or any(part in ("", ".", "..") for part in relative_parts):
                msg = f"Invalid path in source archive: {entry.filename}"
                raise RuntimeError(msg)
            destination = (target_dir / Path(*relative_parts)).resolve()
            if os.path.commonpath([str(destination), str(target_dir)]) != str(target_dir):
                msg = f"Invalid path in source archive: {entry.filename}"
                raise RuntimeError(msg)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with z.open(entry, "r") as source, destination.open("wb") as dest:
                shutil.copyfileobj(source, dest)


async def call_api(url: str, params: dict) -> str:
    """Call the GitHub code scanning API to fetch alert."""
    headers = {
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {GH_TOKEN}",
    }

    async def _fetch_file(url, headers, params):
        try:
            async with httpx.AsyncClient(headers=headers) as client:
                r = await client.get(url, params=params, follow_redirects=True)
                r.raise_for_status()
                return r
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except json.JSONDecodeError as e:
            return f"JSON error: {e}"
        except httpx.HTTPStatusError as e:
            return f"HTTP error: {e}"
        except httpx.AuthenticationError as e:
            return f"Authentication error: {e}"

    return await _fetch_file(url, headers=headers, params=params)


def _parse_content_disposition_filename(header: str | None) -> str | None:
    """Extract the filename from a Content-Disposition header value."""
    if not header:
        return None
    for raw_part in header.split(";"):
        part = raw_part.strip()
        if part.lower().startswith("filename="):
            filename = part.split("=", 1)[1].strip().strip('"')
            return filename
    return None


async def _fetch_source_zip(owner: str, repo: str, tmp_dir):
    """Fetch the source code."""
    url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {GH_TOKEN}",
    }
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, headers=headers, follow_redirects=True) as response:
                response.raise_for_status()
                content_disposition = response.headers.get("content-disposition")
                source_filename = _parse_content_disposition_filename(content_disposition)
                expected_path = _source_archive_path(owner, repo, tmp_dir)
                resolved_path = expected_path.resolve()
                if os.path.commonpath([resolved_path, Path(tmp_dir).resolve()]) != str(Path(tmp_dir).resolve()):
                    return f"Error: Invalid path for source code: {expected_path}"
                if not Path(f"{tmp_dir}/{owner}").exists():
                    os.makedirs(f"{tmp_dir}/{owner}", exist_ok=True)
                async with aiofiles.open(expected_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
        _safe_extract_source_zip(expected_path, _source_extract_path(tmp_dir))
        metadata = {"source_filename": source_filename}
        metadata_path = Path(tmp_dir) / owner / f"{repo}_source_metadata.json"
        async with aiofiles.open(metadata_path, "w") as f:
            await f.write(json.dumps(metadata, indent=2))

        return f"source code for {repo} fetched and extracted successfully."
    except httpx.RequestError as e:
        return f"Error: Request error: {e}"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP error: {e}"
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"


@mcp.tool()
async def fetch_repo_from_gh(owner: str, repo: str):
    """
    Download the source code from GitHub to the local file system to speed up file search.
    """
    owner = owner.lower()
    repo = repo.lower()

    result = await _fetch_source_zip(owner, repo, LOCAL_GH_DIR)
    source_path = _source_archive_path(owner, repo, LOCAL_GH_DIR)
    if not source_path.exists():
        return result

    return f"Downloaded source code to {owner}/{repo}.zip and extracted it to {SOURCE_WORKSPACE_DIR}"


@mcp.tool()
async def clear_local_repo(owner: str, repo: str):
    """
    Delete the local repo.
    """
    owner = owner.lower()
    repo = repo.lower()

    source_path = _source_archive_path(owner, repo, LOCAL_GH_DIR)
    source_path = sanitize_file_path(source_path, [LOCAL_GH_DIR])
    if not source_path:
        return f"Invalid {owner} and {repo}. Check that the input is correct or try to fetch the repo from gh first."
    if source_path.exists():
        os.remove(source_path)
    metadata_path = sanitize_file_path(Path(LOCAL_GH_DIR) / owner / f"{repo}_source_metadata.json", [LOCAL_GH_DIR])
    if metadata_path and metadata_path.exists():
        os.remove(metadata_path)
    extracted_path = _source_extract_path(LOCAL_GH_DIR)
    extracted_path = sanitize_file_path(extracted_path, [LOCAL_GH_DIR])
    if extracted_path and extracted_path.exists():
        shutil.rmtree(extracted_path)
    return f"Cleared the locally stored {owner}/{repo}"


if __name__ == "__main__":
    mcp.run(show_banner=False)
