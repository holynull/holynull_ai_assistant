from hashlib import sha1
import re
from urllib.parse import urlparse
from langchain.agents import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import (
    ChatPromptTemplate,
)
from langchain_core.output_parsers import StrOutputParser
import os
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import ConfigurableField
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_mistralai.chat_models import ChatMistralAI
from langchain_cohere import ChatCohere
from pathlib import Path
import sys

from dotenv import load_dotenv

from typing import Set, Dict
import pathspec
import json

if getattr(sys, "frozen", False):
    script_location = Path(sys.executable).parent.resolve()
else:
    script_location = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_location / ".env")

llm = ChatAnthropic(
    model="claude-3-opus-20240229",
    # max_tokens=,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    verbose=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="model"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="anthropic_claude_3_opus",
    anthropic_claude_3_5_sonnet=ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
        max_tokens=2000,
        temperature=0.9,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        stream_usage=True,
        verbose=True,
    ),
    openai_gpt_3_5_turbo_1106=ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        verbose=True,
        streaming=True,
        temperature=0.9,
    ),
    openai_gpt_4_turbo_preview=ChatOpenAI(
        temperature=0.9,
        model="gpt-4-turbo-2024-04-09",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_4o=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_4o_mini=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o-mini",
        verbose=True,
        streaming=True,
    ),
    pplx_sonar_medium_chat=ChatPerplexity(
        model="sonar-medium-chat", temperature=0.9, verbose=True, streaming=True
    ),
    mistral_large=ChatMistralAI(
        model="mistral-large-latest", temperature=0.9, verbose=True, streaming=True
    ),
    command_r_plus=ChatCohere(
        model="command-r-plus", temperature=0.9, verbose=True, streaming=True
    ),
)

from langchain_community.document_loaders import TextLoader


@tool
def load_file(path: str) -> str:
    """
    Useful when you need load file's content.
    """
    if os.path.exists(path=path):
        loader = TextLoader(path)
        docs = loader.load()
        return "\n".join([doc.page_content for doc in docs])
    return f"Path not exsits. {path}"


import shutil


@tool
def copy_file_in_same_directory(source_path, new_filename=None):
    """
    Copy a file within the same directory.

    Parameters:
    source_path (str): The full path of the source file
    new_filename (str, optional): The new filename. If not provided, a new name will be automatically generated.

    Returns:
    str: If the copy is successful, returns the full path of the new file; if it fails, returns None
    """
    try:
        # Ensure the source file exists
        if not os.path.exists(source_path):
            print(f"Error: Source file '{source_path}' does not exist.")
            return None

        # Get the directory and filename of the source file
        directory = os.path.dirname(source_path)
        filename = os.path.basename(source_path)

        # If no new filename is provided, generate one automatically
        if new_filename is None:
            name, extension = os.path.splitext(filename)
            new_filename = f"{name}_copy{extension}"

        # Ensure the new filename is not the same as the original filename
        if new_filename == filename:
            print("Error: New filename is the same as the original filename.")
            return None

        # Construct the full path of the new file
        new_file_path = os.path.join(directory, new_filename)

        # Copy the file
        shutil.copy2(source_path, new_file_path)
        print(f"File successfully copied: '{new_file_path}'")
        return new_file_path

    except PermissionError:
        print(
            f"Error: Permission denied to copy the file. Please check file permissions."
        )
    except Exception as e:
        print(f"An error occurred: {e}")

    return None


def copy_file(source_path, new_filename=None):
    directory, original_filename = os.path.split(source_path)
    if not new_filename:
        new_filename = f"copy_of_{original_filename}"
    new_file_path = os.path.join(directory, new_filename)
    shutil.copy2(source_path, new_file_path)
    return new_file_path


def apply_suggestions_to_file(file_path, suggestions):
    with open(file_path, "r") as file:
        lines = file.readlines()

    # Sort suggestions by line number
    suggestions.sort(key=lambda x: x["line_number"])

    # Track the offset caused by insertions and deletions
    offset = 0

    for suggestion in suggestions:
        line_number = suggestion["line_number"] + offset
        new_code = suggestion["new_code"]
        operation_type = suggestion.get(
            "type", "update"
        )  # Default to update if not specified

        if 0 <= line_number < len(lines):
            if operation_type == "insert":
                lines.insert(line_number, new_code + "\n")
                offset += 1
            elif operation_type == "delete":
                lines.pop(line_number)
                offset -= 1
            else:  # update
                lines[line_number] = new_code + "\n"

    with open(file_path, "w") as file:
        file.writelines(lines)


@tool
def get_code_modification_suggestions(question: str, file_path: str) -> any:
    """
    Useful when you need generate code modification suggestions.
    """
    prompt_template = """
You are an expert software engineer. Your task is to review given source code and make modifications based on specified issues or improvements. For each modification, you should provide the following details in the specified format:

- line_number: The line number where the modification should be made (0-based index).
- type: The type of modification (insert, update, or delete).
- new_code: The new code that should replace the existing line or be inserted at the specified line number.

If you need to delete a line, set `new_code` to an empty string and `type` to "delete".

Note: *When making multiple modifications, consider that line numbers will change sequentially based on previous insertions or deletions.*

The suggestions should be in the following JSON format:
[
    {{"line_number": LINE_NUMBER, "type": "TYPE", "new_code": "NEW_CODE"}},
    {{"line_number": LINE_NUMBER, "type": "TYPE", "new_code": "NEW_CODE"}}
]

Here are some examples of different types of modifications:
1. Modify an existing line:
    Original Line (line 5): "x = 10"
    Suggestion: {{"line_number": 5, "type": "update", "new_code": "x = 20"}}

2. Insert a new line:
    Original Line (line 3): "y = 5"
    Suggestion: {{"line_number": 4, "type": "insert", "new_code": "print(y)"}}

3. Delete an existing line:
    Original Line (line 8): "z = 30"
    Suggestion: {{"line_number": 8, "type": "delete", "new_code": ""}}

Here is the source code and the issues/improvements that need to be addressed:
```
{source_code}
```

The issues and improvement requirements are as follows:
{question}

Please provide your suggestions in the specified JSON format, ensuring that each suggestion includes the "type" field with one of the values: "insert", "update", or "delete".
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    result = chain.invoke(
        {
            "source_code": load_file.invoke({"path": file_path}),
            "question": question,
        },
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    return result


@tool
def apply_gpt_suggestions(source_file_path, suggestions, new_filename=None):
    """
    Apply the given modification suggestions to the copy of file.
    Parameters:
    source_code (str): The original source code as a single string.
    suggestions (list): A list of suggestions where each suggestion is a dictionary
                        with the following keys:
                        - line_number (int): The 0-based index of the line to be modified.
                        - new_code (str): The new code that should replace the existing
                                          line or be inserted at the specified line number.
                                          If this is an empty string, the existing line
                                          will be deleted.
    Returns:
    str: The modified source code with all of the suggestions applied.
    """
    try:
        copied_file_path = copy_file(source_file_path, new_filename)
        apply_suggestions_to_file(copied_file_path, suggestions)
        return copied_file_path
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


@tool
def get_workspace_dir() -> str:
    """Usefule when you need get the current workspace directory."""
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
def write_to_file(file_path, content, append=False):
    """
    Write normal text content to a specified file.

    Parameters:
    -----------
    file_path : str
        The path of the file to write to. Must be a valid file path.
    content : str
        The content to write to the file.
    append : bool, optional
        If True, append to the end of the file if it exists;
        if False, only write to new files (default).

    Returns:
    --------
    str
        A message describing the operation result.
    """
    # 验证输入参数
    if not isinstance(file_path, str) or not file_path:
        return "file_path must be a non-empty string"
    if not isinstance(content, str):
        return "content must be a string"

    try:
        # 确保使用绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        # 检查文件是否存在
        file_exists = os.path.exists(file_path)
        if file_exists and not append:
            return f"Error: Cannot write to existing file '{file_path}'. Use append=True to append content."

        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 确定写入模式并写入内容
        mode = "a" if append else "w"
        with open(file_path, mode, encoding="utf-8") as file:
            file.write(content)

        # 准备返回信息
        operation_type = "appended to" if append else "written to"
        message = f"Successfully {operation_type} file '{file_path}'"

        # 只在追加模式下提供继续写入的建议
        if append:
            message += "\nYou can continue to append more content using append=True"

        message += f"\nFile path: {file_path}"

        return message

    except IOError as e:
        return f"Error writing to file: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


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


@tool
def generate_git_patch_and_apply(
    file_path: str,
    patch_file_name: str,
    changes=None,
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
    if changes is None or not isinstance(changes, list):
        return """Error: `changes` is required. `changes` list of change information in the format:
            [
                {
                    'line': int,       # Line number to modify
                    'old': str,        # Original content
                    'new': str,        # New content
                    'type': str        # Change type: 'modify', 'add', or 'delete'
                },
                ...
            ]"""
    import os
    from hashlib import sha1
    import json

    try:
        # Read all lines with their line endings
        with open(file_path, "r", encoding="utf-8") as f:
            raw_lines = list(f)
    except Exception as e:
        return f"An error occurred while reading '{file_path}': {e}"

    workspe_dir = get_workspace_dir.invoke({})
    if not is_path_under_workspace(file_path, workspe_dir):
        return f"Error:  Cannot create files outside of workspace. Workspace is {workspe_dir}"
    output_path = workspe_dir + "/patches/" + patch_file_name
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
            source_data = line_contents_ctx[err_line_number]
            base_name = os.path.basename(file_path)
            result = {
                "success": False,
                "patch_content": patch_content,
                "message": f"Check the patch file ({output_path}) failed.\n{e}\n{base_name} in line:{err_line_number} content is:\n{json.dumps(source_data)}",
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
from git.exc import GitCommandError
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
        return f"Error:  Cannot create files outside of workspace. Workspace is {workspace_dir}"
    if not is_path_under_workspace(source_file, workspace_dir):
        return f"Error:  Cannot create files outside of workspace. Workspace is {workspace_dir}"

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


tools = [
    get_workspace_dir,
    list_workspace_directory,
    # load_file,
    # write_to_file,
    create_empty_file,
    get_file_contents,
    generate_git_patch_and_apply,
    # apply_patch_with_git,
    # apply_gpt_suggestions,
    # get_code_modification_suggestions,
]
