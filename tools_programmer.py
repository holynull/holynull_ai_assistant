from hashlib import sha1
import re
from langchain.agents import tool
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from typing import Dict
import pathspec
import json

if getattr(sys, "frozen", False):
    script_location = Path(sys.executable).parent.resolve()
else:
    script_location = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_location / ".env")


@tool
def get_workspace_dir() -> str:
    """Get the current workspace directory."""
    return os.getenv("WORKSPACE_DIR")


@tool
def list_workspace_directory(workspace_dir: str) -> str:
    """
    Generate a tree-like string representation of the workspace directory structure,
    respecting .gitignore rules.

    Args:
        workspace_dir (str): The path to the directory to be listed

    Returns:
        str: A formatted string representing the directory structure where:
            - Directories are shown as [directory_name]
            - Files are shown by their names
            - Each level is indented with 4 spaces
            - Files/directories in .gitignore are excluded
            - Hidden directories are excluded
    """
    directory = Path(workspace_dir)
    result = []

    # 存储每个目录对应的gitignore规则
    gitignore_specs: Dict[Path, pathspec.PathSpec] = {}

    def load_gitignore(dir_path: Path) -> pathspec.PathSpec:
        """加载指定目录的.gitignore规则"""
        gitignore_file = dir_path / ".gitignore"
        if gitignore_file.exists():
            with gitignore_file.open("r", encoding="utf-8") as f:
                return pathspec.PathSpec.from_lines("gitwildmatch", f)
        return pathspec.PathSpec([])

    def is_ignored(path: Path, relative_to: Path) -> bool:
        """检查文件是否被任意层级的.gitignore规则忽略"""
        current = relative_to
        while current >= directory:
            if current in gitignore_specs:
                rel_path = str(path.relative_to(current))
                if gitignore_specs[current].match_file(rel_path):
                    return True
            current = current.parent
        return False

    def build_tree(current_dir: Path, level: int = 0):
        """递归构建目录树"""
        # 加载当前目录的gitignore规则
        gitignore_specs[current_dir] = load_gitignore(current_dir)

        # 添加当前目录名
        result.append("    " * level + f"[{current_dir.name}]")

        # 获取并排序目录内容
        items = sorted(
            current_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
        )

        for item in items:
            # 始终显示.gitignore文件
            if item.name == ".gitignore":
                result.append("    " * (level + 1) + item.name)
                continue

            # 跳过隐藏目录
            if item.is_dir() and item.name.startswith("."):
                continue

            # 检查是否被忽略
            if is_ignored(item, current_dir):
                continue

            if item.is_file():
                result.append("    " * (level + 1) + item.name)
            elif item.is_dir():
                build_tree(item, level + 1)

    build_tree(directory)
    return "\n".join(result)


def generate_git_patch(file_path: str, changes: list) -> str:
    """
    Generate a git patch format string from changes list

    Args:
        file_path: Path of the file being modified
        changes: List of change dictionaries with format:
                {
                    'line': int,       # Line number to modify
                    'old': str,        # Original content
                    'new': str,        # New content
                    'type': str        # Change type: 'modify', 'add', or 'delete'
                }

    Returns:
        str: Git patch format string
    """
    # Sort changes by line number
    changes = sorted(changes, key=lambda x: x["line"])

    # Generate patch header
    patch = [
        f"diff --git a/{file_path} b/{file_path}",
        f"--- a/{file_path}",
        f"+++ b/{file_path}",
    ]

    current_hunk = []
    current_line = 1
    hunk_start = None
    old_lines = 0
    new_lines = 0

    for change in changes:
        # Start a new hunk if needed
        if hunk_start is None:
            hunk_start = change["line"]

        # Add context lines if there's a gap
        while current_line < change["line"]:
            current_hunk.append(f' {" "}')  # Context line
            current_line += 1
            old_lines += 1
            new_lines += 1

        # Add the change
        if change["type"] == "modify":
            current_hunk.append(f'-{change["old"]}')
            current_hunk.append(f'+{change["new"]}')
            old_lines += 1
            new_lines += 1
            current_line += 1
        elif change["type"] == "add":
            current_hunk.append(f'+{change["new"]}')
            new_lines += 1
            current_line += 1
        elif change["type"] == "delete":
            current_hunk.append(f'-{change["old"]}')
            old_lines += 1
            current_line += 1

    # Add hunk header
    if current_hunk:
        hunk_header = f"@@ -{hunk_start},{old_lines} +{hunk_start},{new_lines} @@"
        patch.append(hunk_header)
        patch.extend(current_hunk)

    return "\n".join(patch)


def get_file_contents_ctx(file_path, context_lines=3):
    """
    Read file and return content data with position information (optimized for git patch)

    Args:
        file_path (str): the full path to the file
        context_lines (int): Number of context lines (default 3)

    Returns:
        dict: Dictionary containing file information with separated before/after context
    """
    from pathlib import Path

    workspace = get_workspace_dir.invoke({})
    if not is_path_under_workspace(file_path, workspace):
        raise Exception(
            f"Error:  Cannot read files outside of workspace. Workspace is {workspace}"
        )
    # Read all lines with their line endings
    with open(file_path, "r", encoding="utf-8") as f:
        raw_lines = list(f)

    # Check if file ends with newline
    has_newline = bool(raw_lines and raw_lines[-1].endswith("\n"))

    # Store line endings
    line_endings = []
    for line in raw_lines:
        if line.endswith("\r\n"):
            line_endings.append("\r\n")
        elif line.endswith("\n"):
            line_endings.append("\n")
        else:
            line_endings.append("")

    # Strip line endings for content
    raw_lines = [line.rstrip("\r\n") for line in raw_lines]

    # Process line information
    lines_data = []
    total_lines = len(raw_lines)

    for idx, content in enumerate(raw_lines, start=1):
        # Calculate context line ranges
        before_start = max(0, idx - context_lines - 1)
        before_end = idx - 1
        after_start = idx
        after_end = min(total_lines, idx + context_lines)

        # Extract before context
        before_context = [
            {"number": n + 1, "content": raw_lines[n], "ending": line_endings[n]}
            for n in range(before_start, before_end)
        ]

        # Extract after context
        after_context = [
            {"number": n + 1, "content": raw_lines[n], "ending": line_endings[n]}
            for n in range(after_start, after_end)
        ]

        # Build line information
        line_info = {
            "number": idx,
            "content": content,
            "ending": line_endings[idx - 1],
            "context": {"before": before_context, "after": after_context},
        }

        lines_data.append(line_info)
    doc = {
        "file_path": str(Path(file_path)),
        "lines": lines_data,
        "has_newline": has_newline,
    }
    with open(f"{file_path}.content.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(doc))
    return doc


def generate_git_patch_and_apply(
    file_path: str,
    changes: list = None,
    context_lines: int = 3,
):
    """
    Generate git patch file based on changes.
    Then apply the git patch to the file and save the result to a new file using git's patch application mechanism. (Original file will remain unchanged)

    Args:
        file_path (str): the full file path where the file data from
        patch_file_name (str): file name of patch file
        changes (list): List of change information in the format:
            [
                {
                    'line': int,       # Line number to modify
                    'old': str,        # Original content
                    'new': str,        # New content
                    'type': str        # Change type: 'modify', 'add', or 'delete'
                },
                ...
            ]
        output_path (str): Output file full path
        context_lines (int): Number of context lines

    Returns:
        dict: A dictionary containing the patch application results with the following keys:
            - success (bool): True if patch was applied successfully
            - message (str): Descriptive message about the operation result
            - conflicts (bool): True if there were conflicts during patch application
            - dry_run (bool): True if this was a dry run operation
            - target_file (str): Patch can be successfully applied. A new file will be generated at target_file (Original file will remain unchanged)
    """
    result = {"success": bool, "message": str}
    if changes is None or not isinstance(changes, list) or len(changes) == 0:
        return {
            "success": False,
            "message": """Error: `changes` is required. `changes` list of change information in the format:
            [
                {
                    'line': int,       # Line number to modify
                    'old': str,        # Original content
                    'new': str,        # New content
                    'type': str        # Change type: 'modify', 'add', or 'delete'
                },
                ...
            ]""",
        }
    import os
    from hashlib import sha1
    import json

    try:
        # Read all lines with their line endings
        with open(file_path, "r", encoding="utf-8") as f:
            raw_lines = list(f)
    except Exception as e:
        return {
            "success": False,
            "message": f"An error occurred while reading '{file_path}': {e}",
        }

    workspe_dir = get_workspace_dir.invoke({})
    if not is_path_under_workspace(file_path, workspe_dir):
        return {
            "success": False,
            "message": f"Error:  Cannot create files outside of workspace. Workspace is {workspe_dir}",
        }
    output_path = workspe_dir + "/patches/" + os.path.basename(file_path) + ".patch"
    # Save changes for reference
    os.makedirs(os.path.dirname(workspe_dir + "/patches/"), exist_ok=True)
    # with open(f"{output_path}.change.json", "w", encoding="utf-8") as f:
    #     f.write(json.dumps(changes))

    # Create line lookup
    file_data = get_file_contents_ctx(file_path, context_lines)
    line_contents = {
        line["number"]: line["content"].rstrip("\n") for line in file_data["lines"]
    }
    line_contents_ctx = {line["number"]: line for line in file_data["lines"]}

    # Sort changes by line number
    changes = sorted(changes, key=lambda x: x["line"])

    # Generate patch header
    relative_path = os.path.relpath(file_path, workspe_dir)
    old_hash = sha1(b"old").hexdigest()[:7]
    new_hash = sha1(b"new").hexdigest()[:7]

    patch_lines = [
        f"diff --git a/{relative_path} b/{relative_path}",
        f"index {old_hash}..{new_hash} 100644",
        f"--- a/{relative_path}",
        f"+++ b/{relative_path}",
    ]

    # Group changes into hunks
    hunks = []
    current_hunk = []

    for i, change in enumerate(changes):
        if i == 0 or change["line"] - changes[i - 1]["line"] > 2 * context_lines:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = []
        current_hunk.append(change)

    if current_hunk:
        hunks.append(current_hunk)

    # Process each hunk
    for hunk in hunks:
        hunk_start = max(1, hunk[0]["line"] - context_lines)
        hunk_end = hunk[-1]["line"] + context_lines

        # Calculate hunk line counts
        old_lines = 0
        new_lines = 0

        # Track which lines are modified/added/deleted
        modified_lines = set()
        for change in hunk:
            if change["type"] == "modify":
                old_count = len(change["old"].splitlines())
                new_count = len(change["new"].splitlines())
                old_lines += old_count
                new_lines += new_count
                for i in range(old_count):
                    modified_lines.add(change["line"] + i)
            elif change["type"] == "add":
                new_lines += len(change["new"].splitlines())
            elif change["type"] == "delete":
                old_lines += 1
                modified_lines.add(change["line"])

        # Add context lines that aren't modified
        for line_num in range(hunk_start, hunk_end + 1):
            if line_num in line_contents and line_num not in modified_lines:
                old_lines += 1
                new_lines += 1

        # Generate hunk header
        hunk_header = f"@@ -{hunk_start},{old_lines} +{hunk_start},{new_lines} @@"
        hunk_lines = [hunk_header]

        # Generate hunk content
        current_line = hunk_start
        for change in hunk:
            # Add context before change
            while current_line < change["line"]:
                if current_line in line_contents:
                    hunk_lines.append(f" {line_contents[current_line]}")
                current_line += 1

            if change["type"] == "modify":
                # Remove old lines
                for line in change["old"].splitlines():
                    hunk_lines.append(f"-{line}")
                # Add new lines
                for line in change["new"].splitlines():
                    hunk_lines.append(f"+{line}")
                current_line += 1
            elif change["type"] == "add":
                # Add new lines
                for line in change["new"].splitlines():
                    hunk_lines.append(f"+{line}")
            elif change["type"] == "delete":
                # Remove old line
                if current_line in line_contents:
                    hunk_lines.append(f"-{line_contents[current_line]}")
                current_line += 1

        # Add remaining context
        while current_line <= hunk_end:
            if current_line in line_contents:
                hunk_lines.append(f" {line_contents[current_line]}")
            current_line += 1

        patch_lines.extend(hunk_lines)

    # Write patch file
    patch_content = "\n".join(patch_lines) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(patch_content)
    # Check patch in workspace directory
    current_dir = os.getcwd()
    try:
        os.chdir(workspe_dir)
        git = Git(workspe_dir)
        git.apply("--check", output_path)
        return apply_patch_with_git(patch_file=output_path, source_file=file_path)
    except Exception as e:

        def extract_line_number(error_text):
            try:
                # 匹配任意文件名后跟着冒号和数字的模式
                pattern = r"error: patch failed: .*?:(\d+)"
                match = re.search(pattern, error_text)
                if match:
                    return int(match.group(1))
                return None
            except Exception:
                return None

        err_line_number = extract_line_number(f"{e}")
        err_line_number = (
            err_line_number + context_lines if err_line_number is not None else None
        )
        if err_line_number is not None:
            if err_line_number not in line_contents_ctx:
                err_line_number = err_line_number - context_lines
            if err_line_number in line_contents_ctx:
                source_data = line_contents_ctx[err_line_number]
            base_name = os.path.basename(file_path)
            result = {
                "success": False,
                "patch_content": patch_content,
                "message": (
                    f"Check the patch file ({output_path}) failed.\n"
                    f"{e}\n{base_name} in line:{err_line_number} content is:\n{json.dumps(source_data) if source_data else ''}"
                ),
            }
            return result
        else:
            result = {
                "success": False,
                "patch_content": patch_content,
                "message": f"Check the patch file ({output_path}) failed.\n{e}",
            }
            return result
    finally:
        os.chdir(current_dir)


import shutil
import tempfile
from contextlib import contextmanager
from git import Git, Repo
from pathlib import Path


@contextmanager
def temporary_git_repo(workspace: str = None):
    """Create a temporary git repository and clean it up when done.

    Yields:
        tuple: (Repo object, temporary directory path)
    """
    temp_dir = tempfile.mkdtemp(dir=workspace)
    repo = Repo.init(temp_dir)
    try:
        yield repo, temp_dir
    finally:
        shutil.rmtree(temp_dir)


def is_path_under_workspace(file_path, workspace_path):
    # 获取两个路径的绝对路径
    abs_file = os.path.abspath(file_path)
    abs_workspace = os.path.abspath(workspace_path)

    # 使用 os.path.commonpath 比较
    try:
        common_path = os.path.commonpath([abs_file, abs_workspace])
        return common_path == abs_workspace
    except ValueError:  # 当路径在不同驱动器时会抛出异常
        return False


def validate_paths(*paths):
    """Validate that all provided paths exist.

    Args:
        *paths: Variable number of paths to validate

    Raises:
        FileNotFoundError: If any path doesn't exist
    """
    for path in paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")


def apply_patch_with_git(
    patch_file: str,
    source_file: str,
    dry_run: bool = False,
) -> dict:
    """Apply a git patch to a source file and save the result to a new file using git's patch application mechanism. (Original file will remain unchanged)

    Args:
        patch_file (str): full path to the patch file to apply
        source_file (str): full path to the source file to patch
        dry_run (bool): If True, only test if patch can be applied without modifying files

    Returns:
        dict: A dictionary containing the patch application results with the following keys:
            - success (bool): True if patch was applied successfully
            - message (str): Descriptive message about the operation result
            - conflicts (bool): True if there were conflicts during patch application
            - dry_run (bool): True if this was a dry run operation
            - target_file (str): Patch can be successfully applied. A new file will be generated at target_file (Original file will remain unchanged)
    """
    workspace_dir = get_workspace_dir.invoke({})
    if not is_path_under_workspace(patch_file, workspace_dir):
        return {
            "success": False,
            "message": f"Error:  Cannot create files outside of workspace. Workspace is {workspace_dir}",
        }
    if not is_path_under_workspace(source_file, workspace_dir):
        return {
            "success": False,
            "message": f"Error:  Cannot create files outside of workspace. Workspace is {workspace_dir}",
        }

    def _prepare_paths():
        """Prepare and validate all file paths."""
        nonlocal patch_file, source_file, target_file
        validate_paths(patch_file, source_file)
        patch_file = os.path.abspath(patch_file)
        source_file = os.path.abspath(source_file)

        # Calculate target file path
        with open(patch_file, "r", encoding="utf-8") as f:
            patch_content = f.read()
        patch_hash = sha1(patch_content.encode("utf-8")).hexdigest()[:8]

        file_path_obj = Path(source_file)
        target_file = (
            file_path_obj.parent
            / f"{file_path_obj.stem}_{patch_hash}{file_path_obj.suffix}.patched"
        )
        target_file = os.path.abspath(target_file)
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        return patch_content

    def _apply_patch_dry_run(repo, patch_file):
        """Execute dry run patch application."""
        repo.git.apply("--check", patch_file)
        return {
            "success": True,
            "message": f"Patch can be successfully applied. A new file will be generated at: {target_file} (Original file will remain unchanged)",
            "conflicts": False,
            "dry_run": True,
            "target_file": target_file,
        }

    def _apply_patch_real(repo, temp_file):
        """Execute actual patch application."""
        repo.git.apply(patch_file)
        conflicts = False
        message = f"Patch applied successfully. A new file containing the patched result has been generated at: {target_file} (Original file remains unchanged)"

        shutil.copy2(temp_file, target_file)
        return {
            "success": True,
            "message": message,
            "conflicts": conflicts,
            "dry_run": False,
            "target_file": os.path.relpath(target_file, workspace_dir),
        }

    try:
        # Initialize result
        target_file = None

        # Prepare paths and read patch content
        _prepare_paths()

        # Execute in temporary git repository
        with temporary_git_repo() as (repo, temp_dir):
            rel_path = os.path.dirname(os.path.relpath(source_file, workspace_dir))
            temp_target_file = os.path.join(temp_dir, rel_path)
            os.makedirs(temp_target_file, exist_ok=True)
            # Setup initial state
            temp_file = os.path.join(temp_target_file, os.path.basename(source_file))
            shutil.copy2(source_file, temp_file)
            repo.index.add([temp_file])
            repo.index.commit("Initial commit")

            # Apply patch
            if dry_run:
                result = _apply_patch_dry_run(repo, patch_file)
            else:
                if os.path.getsize(source_file) == 0:
                    current_dir = os.getcwd()
                    try:
                        os.chdir(workspace_dir)
                        git = Git(workspace_dir)
                        git.apply(patch_file)
                    except Exception as e:
                        return {
                            "success": False,
                            "message": f"Patch failed. {e}",
                        }
                    finally:
                        os.chdir(current_dir)
                    return {
                        "success": True,
                        "message": f"Patch applied successfully.",
                    }
                else:
                    result = _apply_patch_real(repo, temp_file)

        return result

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to apply patch: {str(e)}",
            "dry_run": False,
        }


@tool
def generate_new_version_file(file_path: str):
    """Generate a new version of the file based on the modification requirements.
    Execute a file modification task, which will eventually modify the file on the copy of the file.
    First, performs generates the change list data, then generates a git patch based on the change list data, and finally applies the git patch to the copy of the file.
    Change list is in the format as follow:
        [
            {
                'line': int,       # Line number to modify
                'old': str,        # Original content
                'new': str,        # New content
                'type': str        # Change type: 'modify', 'add', or 'delete'
            },
            ...
        ]

    Args:
        file_path (str): The full path of the source file.

        Returns:
        dict: A dictionary containing the patch application results with the following keys:
            - success (bool): True if patch was applied successfully
            - message (str): Descriptive message about the operation result
            - conflicts (bool): True if there were conflicts during patch application
            - dry_run (bool): True if this was a dry run operation
            - target_file (str): Patch can be successfully applied. A new file will be generated at target_file (Original file will remain unchanged)
    """
    return file_path


@tool
def create_empty_file(file_path: str) -> str:
    """
    Create a new empty file in workspace, if it doesn't exist.

    Args:
        file_path (str): The path where the empty file should be created.
            Can be either absolute or relative path.

    Returns:
        str: A string indicating the operation result:
            - "file_exists": If the file already exists
            - "success": If the file was created successfully
            - "error: [error message]": If the creation failed, including the specific error message
    """
    try:
        # Check if file already exists
        if os.path.exists(file_path):
            return f"Error: {file_path} file exists."
        workspace = get_workspace_dir.invoke({})
        if not is_path_under_workspace(file_path, workspace):
            return f"Error:  Cannot create files outside of workspace. Workspace is {workspace}"

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        # Create empty file
        with open(file_path, "w") as f:
            pass
        return f"Create file success. The path is {file_path}"

    except OSError as e:
        return f"error: {str(e)}"


@tool
def run_one_step(name: str, description: str, file_path: str):
    """Perform one code modification step of the step-by-step tasks to complete programming requirements

    Args:
                name (str): Step's name
        description: Description of the steps and what needs to be achieved
    """
    return {"name": name, "description": description, "file_path": file_path}


@tool
def design_code_modification_plan(data: list[dict]):
    """After analyzing the code, design a step-by-step plan for modifying the code that contains only the specific steps to modify the code. 
    Note: The step descriptions must be specific and unambiguous.

    Args:
            data (list[dict]): Data of plan.
                Element in the list is a dict with:
                - name (str): Step's name.
                - description(str):Description of the steps and what needs to be achieved about source code.
    """
    return data


tools = [
    # generate_new_version_file,
    # create_empty_file,
    design_code_modification_plan,
    run_one_step,
]
