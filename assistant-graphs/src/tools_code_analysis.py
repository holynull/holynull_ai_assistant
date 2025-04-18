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


@tool
def get_file_contents(file_path):
    """
    Read file and return content data with position information (optimized for git patch)

    Args:
        file_path (str): the full path to the file

    Returns:
        dict: Dictionary containing file information
    """
    from pathlib import Path

    workspace = get_workspace_dir.invoke({})
    if not is_path_under_workspace(file_path, workspace):
        return (
            f"Error:  Cannot read files outside of workspace. Workspace is {workspace}"
        )
    try:
        # Read all lines with their line endings
        with open(file_path, "r", encoding="utf-8") as f:
            raw_lines = list(f)
    except Exception as e:
        return f"An error occurred while reading '{file_path}': {e}"

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

    for idx, content in enumerate(raw_lines, start=1):

        # Build line information
        line_info = {
            "number": idx,
            "content": content,
            "ending": line_endings[idx - 1],
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


tools = [
    get_workspace_dir,
    list_workspace_directory,
    get_file_contents,
]
