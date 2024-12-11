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
def write_to_file(file_path, file_name, content, append=False):
    """
    Write normal text content to a specified file.

    Parameters:
    file_path (str): The path of the file to write to
    file_name (str): The name of the file to write to
    content (str): The content to write
    append (bool, optional): If True, append to the end of the file; if False, overwrite the file. Default is False.

    Returns:
    str: Returns a message describing the operation result and suggestions for next steps
    """

    try:
        # Determine the write mode
        mode = "a" if append else "w"

        # Construct full file path using os.path.join
        full_path = os.path.join(file_path, file_name)

        # 确保目录存在
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Open the file and write the content
        with open(full_path, mode, encoding="utf-8") as file:
            file.write(content)

        # 准备返回信息
        operation_type = "appended to" if append else "written to"
        message = f"Successfully {operation_type} file '{full_path}'"

        # 如果还有剩余内容未写入，添加建议信息
        message += f"\nPlease check if there is any remaining content that needs to be written to the file. If so, please call this function again with the remaining content and append=True"
        message += f"\nThe current file path is: {full_path}"

        return message

    except IOError as e:
        return f"An IOError occurred while writing to '{full_path}': {e}"
    except Exception as e:
        return f"An error occurred while writing to '{full_path}': {e}"


@tool
def get_file_contents(file_path, context_lines=3):
    """
    Read file and return content data with position information (optimized for git patch)

    Args:
        file_path (str): Path to the file
        context_lines (int): Number of context lines (default 3)

    Returns:
        dict: Dictionary containing file information with separated before/after context
    """
    from pathlib import Path

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

    return {
        "file_path": str(Path(file_path)),
        "lines": lines_data,
        "has_newline": has_newline,
    }


@tool
def generate_git_patch(file_path, changes, output_path, context_lines=3):
    """
    Generate git patch file, which based on the file and change information.

    Args:
        file_path (str): Path to the file
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
        output_path (str): Path to write the patch file
        context_lines (int): Number of context lines (default 3)

    Returns:
        str: Path of the written patch file
    """
    import os
    from hashlib import sha1
    from datetime import datetime

    def format_range(start, count):
        """Format patch range marker"""
        if count == 1:
            return str(start)
        return f"{start},{count}"

    def normalize_line_endings(text):
        """Normalize line endings to LF"""
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def split_into_lines(text):
        """Split text into lines, preserving empty lines"""
        return text.split("\n")

    # Sort changes by line number
    changes = sorted(changes, key=lambda x: x["line"])

    # Get file contents with context
    file_data = get_file_contents.invoke(
        {"file_path": file_path, "context_lines": context_lines}
    )

    # Generate patch header
    file_path = os.path.normpath(file_data["file_path"])
    # Generate some dummy hashes for index line
    old_hash = sha1(b"old").hexdigest()[:7]
    new_hash = sha1(b"new").hexdigest()[:7]
    patch_lines = [
        f"diff --git a/{file_path} b/{file_path}",
        f"index {old_hash}..{new_hash} 100644",
        f"--- a/{file_path}",
        f"+++ b/{file_path}",
    ]

    # Track line number adjustments
    line_adjustment = 0
    processed_changes = []

    # Process and normalize changes
    for change in changes:
        if "old" in change:
            change["old"] = normalize_line_endings(change["old"])
            old_lines = split_into_lines(change["old"])
        else:
            old_lines = []

        if "new" in change:
            change["new"] = normalize_line_endings(change["new"])
            new_lines = split_into_lines(change["new"])
        else:
            new_lines = []

        adjusted_line = change["line"] + line_adjustment

        # Update line adjustment for subsequent changes
        if change["type"] == "add":
            line_adjustment += len(new_lines)
        elif change["type"] == "delete":
            line_adjustment -= len(old_lines)
        elif change["type"] == "modify":
            line_adjustment += len(new_lines) - len(old_lines)

        processed_changes.append(
            {
                "line": adjusted_line,
                "old_lines": old_lines,
                "new_lines": new_lines,
                "type": change["type"],
            }
        )

    # Group nearby changes into hunks
    hunks = []
    current_hunk = []
    last_line = 0

    for change in processed_changes:
        if current_hunk and change["line"] > last_line + 2 * context_lines:
            hunks.append(current_hunk)
            current_hunk = []

        current_hunk.append(change)
        last_line = change["line"]

    if current_hunk:
        hunks.append(current_hunk)

    # Process each hunk
    for hunk in hunks:
        first_change = hunk[0]
        last_change = hunk[-1]

        # Calculate hunk range
        hunk_start = max(1, first_change["line"] - context_lines)
        hunk_end = last_change["line"] + context_lines

        # Calculate line counts for hunk header
        old_count = hunk_end - hunk_start + 1
        new_count = old_count

        # Adjust counts based on changes
        for change in hunk:
            if change["type"] == "add":
                new_count += len(change["new_lines"])
            elif change["type"] == "delete":
                old_count += len(change["old_lines"]) - 1
                new_count -= 1
            elif change["type"] == "modify":
                new_count += len(change["new_lines"]) - len(change["old_lines"])

        # Generate hunk header
        hunk_header = f"@@ -{format_range(hunk_start, old_count)} +{format_range(hunk_start, new_count)} @@"
        hunk_lines = [hunk_header]

        # Process each line in the hunk
        current_line = hunk_start
        for change in hunk:
            # Add context lines before change
            while current_line < change["line"]:
                context_line = next(
                    (
                        line
                        for line in file_data["lines"]
                        if line["number"] == current_line
                    ),
                    None,
                )
                if context_line:
                    content = context_line["content"].rstrip("\n")
                    hunk_lines.append(f" {content}")
                current_line += 1

            # Add the change
            if change["type"] in ("delete", "modify"):
                for line in change["old_lines"]:
                    hunk_lines.append(f"-{line}")

            if change["type"] in ("add", "modify"):
                for line in change["new_lines"]:
                    hunk_lines.append(f"+{line}")

            current_line += 1 if change["type"] != "add" else 0

        # Add remaining context lines
        context_end = min(hunk_end, len(file_data["lines"]))
        while current_line <= context_end:
            context_line = next(
                (line for line in file_data["lines"] if line["number"] == current_line),
                None,
            )
            if context_line:
                content = context_line["content"].rstrip("\n")
                hunk_lines.append(f" {content}")
            current_line += 1

        patch_lines.extend(hunk_lines)
        # 删除了这行: patch_lines.append("")  # Empty line between hunks

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write patch content to file
    patch_content = "\n".join(patch_lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(patch_content)

    return output_path


tools = [
    get_workspace_dir,
    list_workspace_directory,
    # load_file,
    write_to_file,
    get_file_contents,
    # generate_git_patch,
    # apply_gpt_suggestions,
    # get_code_modification_suggestions,
]
