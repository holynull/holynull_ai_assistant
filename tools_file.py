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


@tool
def write_to_file(file_path, content, append=False):
    """
    Write content to a specified file.

    Parameters:
    file_path (str): The path of the file to write to
    content (str): The content to write
    append (bool, optional): If True, append to the end of the file; if False, overwrite the file. Default is False.

    Returns:
    bool: Returns True if the write is successful, otherwise returns False
    """
    try:
        # Determine the write mode
        mode = "a" if append else "w"

        # Open the file and write the content
        with open(file_path, mode, encoding="utf-8") as file:
            file.write(content)

        print(
            f"Content successfully {'appended to' if append else 'written to'} '{file_path}'"
        )
        return True

    except IOError as e:
        print(f"An IOError occurred while writing to the file: {e}")
    except Exception as e:
        print(f"An error occurred while writing to the file: {e}")

    return False


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
        gitignore_file = dir_path / '.gitignore'
        if gitignore_file.exists():
            with gitignore_file.open('r', encoding='utf-8') as f:
                return pathspec.PathSpec.from_lines('gitwildmatch', f)
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
        items = sorted(current_dir.iterdir(), 
                      key=lambda x: (not x.is_dir(), x.name.lower()))
        
        for item in items:
            # 始终显示.gitignore文件
            if item.name == '.gitignore':
                result.append("    " * (level + 1) + item.name)
                continue
                
            # 跳过隐藏目录
            if item.is_dir() and item.name.startswith('.'):
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


tools = [
    get_workspace_dir,
    list_workspace_directory,
    load_file,
    # write_to_file,
    # apply_gpt_suggestions,
    # get_code_modification_suggestions,
]
