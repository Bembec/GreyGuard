"""
GreyGuard V10 controlled tool gateway.

The gateway performs a small set of safe operations only.
It never provides unrestricted terminal, filesystem, or
network access.
"""

from pathlib import Path


project_path = Path(__file__).parent.resolve()

sandbox_root = (
    project_path / "sandbox_data"
).resolve()

security_log_path = (
    project_path / "greyguard_security.log"
).resolve()

maximum_read_bytes = 100_000
maximum_note_bytes = 10_000
maximum_search_results = 50

allowed_tools = {
    "list_files",
    "read_file",
    "write_note",
    "search_logs",
}


class ToolGatewayError(Exception):
    """Raised when a tool operation is unsafe or invalid."""


def initialize_sandbox():
    """Create the controlled sandbox and safe sample data."""

    sandbox_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    notes_directory = (
        sandbox_root / "notes"
    )

    notes_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    public_report_path = (
        sandbox_root / "public_report.txt"
    )

    if not public_report_path.exists():
        public_report_path.write_text(
            (
                "GreyGuard controlled sandbox report.\n"
                "\n"
                "This is a safe demonstration file.\n"
                "Agents may read it only after GreyGuard "
                "authorizes the request.\n"
            ),
            encoding="utf-8",
        )

    instructions_path = (
        sandbox_root / "instructions.txt"
    )

    if not instructions_path.exists():
        instructions_path.write_text(
            (
                "GreyGuard V10 sandbox instructions:\n"
                "\n"
                "1. All file operations remain inside "
                "sandbox_data.\n"
                "2. Unknown tools are blocked.\n"
                "3. Sensitive actions require approval.\n"
                "4. Every execution produces evidence.\n"
            ),
            encoding="utf-8",
        )

    return {
        "sandbox_root": str(sandbox_root),
        "created": True,
    }


def get_supported_tools():
    """Return the tools exposed by this gateway."""

    return sorted(allowed_tools)


def is_path_inside_sandbox(candidate_path):
    """Return whether a resolved path is inside the sandbox."""

    try:
        candidate_path.relative_to(
            sandbox_root
        )
        return True

    except ValueError:
        return False


def normalize_target(target):
    """Validate and resolve a sandbox-relative target."""

    if target is None:
        target = ""

    if not isinstance(target, str):
        raise ToolGatewayError(
            "Target must be a string."
        )

    target = target.strip()

    target_path = Path(target)

    if target_path.is_absolute():
        raise ToolGatewayError(
            "Absolute paths are not permitted."
        )

    candidate_path = (
        sandbox_root / target_path
    ).resolve()

    if not is_path_inside_sandbox(
        candidate_path
    ):
        raise ToolGatewayError(
            "Target escapes the GreyGuard sandbox."
        )

    return candidate_path


def relative_target(target_path):
    """Return a sandbox-relative display path."""

    relative_path = target_path.relative_to(
        sandbox_root
    )

    relative_text = relative_path.as_posix()

    if relative_text == ".":
        return ""

    return relative_text


def validate_existing_target(
    target,
    expected_type=None,
):
    """Resolve a target and confirm that it exists."""

    target_path = normalize_target(target)

    if not target_path.exists():
        raise ToolGatewayError(
            "Requested sandbox target does not exist."
        )

    resolved_path = target_path.resolve()

    if not is_path_inside_sandbox(
        resolved_path
    ):
        raise ToolGatewayError(
            "Resolved target escapes the sandbox."
        )

    if (
        expected_type == "file"
        and not resolved_path.is_file()
    ):
        raise ToolGatewayError(
            "Requested target is not a file."
        )

    if (
        expected_type == "directory"
        and not resolved_path.is_dir()
    ):
        raise ToolGatewayError(
            "Requested target is not a directory."
        )

    return resolved_path


def safe_file_size(file_path):
    """Return the size of a sandbox file."""

    try:
        return file_path.stat().st_size

    except OSError as error:
        raise ToolGatewayError(
            "GreyGuard could not inspect the file."
        ) from error


def list_files(target=""):
    """List files inside one sandbox directory."""

    directory_path = validate_existing_target(
        target,
        expected_type="directory",
    )

    entries = []

    try:
        children = sorted(
            directory_path.iterdir(),
            key=lambda path: path.name.lower(),
        )

    except OSError as error:
        raise ToolGatewayError(
            "GreyGuard could not list the directory."
        ) from error

    for child_path in children:
        resolved_child = child_path.resolve()

        if not is_path_inside_sandbox(
            resolved_child
        ):
            continue

        if child_path.is_symlink():
            entry_type = "SYMLINK_BLOCKED"
            entry_size = None

        elif resolved_child.is_dir():
            entry_type = "DIRECTORY"
            entry_size = None

        elif resolved_child.is_file():
            entry_type = "FILE"
            entry_size = safe_file_size(
                resolved_child
            )

        else:
            entry_type = "OTHER"
            entry_size = None

        entries.append(
            {
                "name": child_path.name,
                "path": relative_target(
                    resolved_child
                ),
                "type": entry_type,
                "size_bytes": entry_size,
            }
        )

    return {
        "success": True,
        "tool": "list_files",
        "target": relative_target(
            directory_path
        ),
        "message": (
            f"Listed {len(entries)} sandbox entries."
        ),
        "data": {
            "entries": entries,
            "entry_count": len(entries),
        },
    }


def read_file(target):
    """Read a UTF-8 text file inside the sandbox."""

    file_path = validate_existing_target(
        target,
        expected_type="file",
    )

    file_size = safe_file_size(file_path)

    if file_size > maximum_read_bytes:
        raise ToolGatewayError(
            "File exceeds the safe reading limit."
        )

    try:
        content = file_path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError as error:
        raise ToolGatewayError(
            "Only UTF-8 text files may be read."
        ) from error

    except OSError as error:
        raise ToolGatewayError(
            "GreyGuard could not read the file."
        ) from error

    return {
        "success": True,
        "tool": "read_file",
        "target": relative_target(file_path),
        "message": "Sandbox file read successfully.",
        "data": {
            "content": content,
            "size_bytes": file_size,
        },
    }


def validate_note_target(target):
    """Validate a note path inside sandbox_data/notes."""

    if not target:
        raise ToolGatewayError(
            "A note filename is required."
        )

    target_path = normalize_target(target)

    notes_root = (
        sandbox_root / "notes"
    ).resolve()

    try:
        target_path.relative_to(notes_root)

    except ValueError as error:
        raise ToolGatewayError(
            "Notes may only be written inside "
            "sandbox_data/notes."
        ) from error

    if target_path.suffix.lower() != ".txt":
        raise ToolGatewayError(
            "Only .txt note files may be written."
        )

    parent_path = (
        target_path.parent
    ).resolve()

    if not is_path_inside_sandbox(
        parent_path
    ):
        raise ToolGatewayError(
            "Note path escapes the sandbox."
        )

    return target_path


def write_note(
    target,
    payload,
    dry_run=False,
):
    """Write a controlled text note inside the sandbox."""

    if not isinstance(payload, dict):
        raise ToolGatewayError(
            "Tool payload must be a JSON object."
        )

    content = payload.get("content")

    if not isinstance(content, str):
        raise ToolGatewayError(
            "The note content must be a string."
        )

    content_size = len(
        content.encode("utf-8")
    )

    if content_size > maximum_note_bytes:
        raise ToolGatewayError(
            "Note exceeds the safe writing limit."
        )

    target_path = validate_note_target(
        target
    )

    overwrite = payload.get(
        "overwrite",
        False,
    )

    if not isinstance(overwrite, bool):
        raise ToolGatewayError(
            "The overwrite value must be true or false."
        )

    if (
        target_path.exists()
        and not overwrite
    ):
        raise ToolGatewayError(
            "Note already exists. Explicit overwrite "
            "permission is required."
        )

    note_target = relative_target(
        target_path
    )

    if dry_run:
        return {
            "success": True,
            "tool": "write_note",
            "target": note_target,
            "message": (
                "Dry run completed. No file was written."
            ),
            "data": {
                "would_write": True,
                "would_overwrite": (
                    target_path.exists()
                ),
                "size_bytes": content_size,
            },
        }

    try:
        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        resolved_parent = (
            target_path.parent.resolve()
        )

        if not is_path_inside_sandbox(
            resolved_parent
        ):
            raise ToolGatewayError(
                "Note directory escapes the sandbox."
            )

        target_path.write_text(
            content,
            encoding="utf-8",
        )

    except ToolGatewayError:
        raise

    except OSError as error:
        raise ToolGatewayError(
            "GreyGuard could not write the note."
        ) from error

    return {
        "success": True,
        "tool": "write_note",
        "target": note_target,
        "message": "Sandbox note written successfully.",
        "data": {
            "size_bytes": content_size,
            "overwritten": overwrite,
        },
    }


def search_logs(payload):
    """Search the GreyGuard security log safely."""

    if not isinstance(payload, dict):
        raise ToolGatewayError(
            "Tool payload must be a JSON object."
        )

    query = payload.get("query")

    if not isinstance(query, str):
        raise ToolGatewayError(
            "A string search query is required."
        )

    query = query.strip()

    if not query:
        raise ToolGatewayError(
            "Search query cannot be empty."
        )

    if len(query) > 200:
        raise ToolGatewayError(
            "Search query is too long."
        )

    if not security_log_path.exists():
        return {
            "success": True,
            "tool": "search_logs",
            "target": (
                security_log_path.name
            ),
            "message": (
                "The security log does not exist yet."
            ),
            "data": {
                "query": query,
                "matches": [],
                "match_count": 0,
                "truncated": False,
            },
        }

    try:
        lines = security_log_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

    except OSError as error:
        raise ToolGatewayError(
            "GreyGuard could not read the security log."
        ) from error

    matches = []

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        if query.casefold() in line.casefold():
            matches.append(
                {
                    "line_number": line_number,
                    "text": line[:500],
                }
            )

        if len(matches) >= maximum_search_results:
            break

    total_match_count = sum(
        query.casefold() in line.casefold()
        for line in lines
    )

    return {
        "success": True,
        "tool": "search_logs",
        "target": security_log_path.name,
        "message": (
            f"Found {total_match_count} matching "
            "security log lines."
        ),
        "data": {
            "query": query,
            "matches": matches,
            "match_count": total_match_count,
            "truncated": (
                total_match_count
                > maximum_search_results
            ),
        },
    }


def preview_tool(
    action,
    target="",
    payload=None,
):
    """Describe a tool operation without executing it."""

    if payload is None:
        payload = {}

    normalized_action = (
        str(action).strip().lower()
    )

    if normalized_action not in allowed_tools:
        raise ToolGatewayError(
            "Unknown or unavailable tool."
        )

    if normalized_action == "list_files":
        directory_path = (
            validate_existing_target(
                target,
                expected_type="directory",
            )
        )

        return {
            "success": True,
            "tool": normalized_action,
            "target": relative_target(
                directory_path
            ),
            "message": (
                "Dry run completed. The directory "
                "would be listed."
            ),
            "data": {
                "would_execute": True,
            },
        }

    if normalized_action == "read_file":
        file_path = validate_existing_target(
            target,
            expected_type="file",
        )

        return {
            "success": True,
            "tool": normalized_action,
            "target": relative_target(
                file_path
            ),
            "message": (
                "Dry run completed. The file "
                "would be read."
            ),
            "data": {
                "would_execute": True,
                "size_bytes": safe_file_size(
                    file_path
                ),
            },
        }

    if normalized_action == "write_note":
        return write_note(
            target=target,
            payload=payload,
            dry_run=True,
        )

    if normalized_action == "search_logs":
        query = payload.get("query")

        if (
            not isinstance(query, str)
            or not query.strip()
        ):
            raise ToolGatewayError(
                "A string search query is required."
            )

        return {
            "success": True,
            "tool": normalized_action,
            "target": security_log_path.name,
            "message": (
                "Dry run completed. The log "
                "would be searched."
            ),
            "data": {
                "would_execute": True,
                "query": query.strip(),
            },
        }

    raise ToolGatewayError(
        "Tool preview is unavailable."
    )


def execute_tool(
    action,
    target="",
    payload=None,
    dry_run=False,
):
    """Execute one approved, controlled tool operation."""

    initialize_sandbox()

    if payload is None:
        payload = {}

    if not isinstance(payload, dict):
        raise ToolGatewayError(
            "Tool payload must be a JSON object."
        )

    normalized_action = (
        str(action).strip().lower()
    )

    if normalized_action not in allowed_tools:
        raise ToolGatewayError(
            "Unknown or unavailable tool."
        )

    if dry_run:
        return preview_tool(
            action=normalized_action,
            target=target,
            payload=payload,
        )

    if normalized_action == "list_files":
        return list_files(target)

    if normalized_action == "read_file":
        return read_file(target)

    if normalized_action == "write_note":
        return write_note(
            target=target,
            payload=payload,
            dry_run=False,
        )

    if normalized_action == "search_logs":
        return search_logs(payload)

    raise ToolGatewayError(
        "Tool execution is unavailable."
    )


if __name__ == "__main__":
    initialize_sandbox()

    print("GreyGuard V10 tool gateway initialized.")
    print("Sandbox:", sandbox_root)
    print("Supported tools:")

    for tool_name in get_supported_tools():
        print("-", tool_name)