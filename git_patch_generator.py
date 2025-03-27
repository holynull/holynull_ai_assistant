from typing import List, Dict, Union, Tuple, Optional, Any
from datetime import datetime
import os
import re
import shutil
from pathlib import Path
import tempfile
from enum import Enum
from dataclasses import dataclass
from difflib import unified_diff
import json
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitPatchError(Exception):
    """Base exception for git patch operations"""

    pass


class PatchConflictError(GitPatchError):
    """Exception for patch conflicts"""

    pass


class PatchFormatError(GitPatchError):
    """Exception for patch format errors"""

    pass


class VerificationResult(Enum):
    """Patch verification result"""

    VALID = "valid"
    CONTEXT_MISMATCH = "context_mismatch"
    CONFLICT = "conflict"
    INVALID_FORMAT = "invalid_format"


@dataclass
class PatchStatistics:
    """Class to hold patch statistics"""

    total_changes: int = 0
    additions: int = 0
    deletions: int = 0
    modifications: int = 0
    conflicts: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_changes": self.total_changes,
            "additions": self.additions,
            "deletions": self.deletions,
            "modifications": self.modifications,
            "conflicts": self.conflicts,
        }

    def __str__(self) -> str:
        return (
            f"Changes: {self.total_changes} total\n"
            f"  + {self.additions} additions\n"
            f"  - {self.deletions} deletions\n"
            f"  ~ {self.modifications} modifications\n"
            f"  ! {self.conflicts} conflicts"
        )


@dataclass
class PatchPreview:
    """Class to hold patch preview information"""

    original_lines: List[str]
    patched_lines: List[str]
    changes: List[Dict[str, str]]
    conflicts: List[Dict[str, str]]
    statistics: PatchStatistics

    def get_preview(self, context_lines: int = 3) -> str:
        """Generate human-readable preview"""
        result = []
        result.append("=== Patch Preview ===\n")

        # Show statistics
        result.append("Statistics:")
        result.append(str(self.statistics))
        result.append("")

        # Show diff
        diff = list(
            unified_diff(
                self.original_lines,
                self.patched_lines,
                fromfile="Original",
                tofile="Patched",
                n=context_lines,
            )
        )
        result.extend(diff)

        # Show changes summary
        if self.changes:
            result.append("\n=== Changes Summary ===")
            for i, change in enumerate(self.changes, 1):
                result.append(f"\n{i}. {change['description']}")

        # Show conflicts if any
        if self.conflicts:
            result.append("\n=== Conflicts ===")
            for i, conflict in enumerate(self.conflicts, 1):
                result.append(f"\n{i}. {conflict['description']}")
                result.append(f"   At line {conflict['line']}")
                result.append(f"   Existing content: {conflict['existing']}")
                result.append(f"   Patch content: {conflict['patch']}")

        return "\n".join(result)

    def to_dict(self) -> Dict[str, Any]:
        """Convert preview to dictionary format"""
        return {
            "statistics": self.statistics.to_dict(),
            "changes": self.changes,
            "conflicts": self.conflicts,
            "original_content": "".join(self.original_lines),
            "patched_content": "".join(self.patched_lines),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert preview to JSON format"""
        return json.dumps(self.to_dict(), indent=indent)


class PatchHunk:
    """Class to represent a patch hunk"""

    def __init__(
        self, start_line: int, old_count: int, new_count: int, content: List[str]
    ):
        self.start_line = start_line
        self.old_count = old_count
        self.new_count = new_count
        self.content = content
        self.changes: List[Dict[str, str]] = []
        self.conflicts: List[Dict[str, str]] = []

    @classmethod
    def parse_header(cls, header: str) -> Tuple[int, int, int]:
        """Parse hunk header like @@ -1,3 +1,4 @@"""
        match = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", header)
        if not match:
            raise PatchFormatError(f"Invalid hunk header: {header}")
        old_start, old_count, new_start, new_count = map(int, match.groups())
        return old_start, old_count, new_count

    def add_change(self, description: str) -> None:
        """Add a change description"""
        self.changes.append({"description": description})

    def add_conflict(
        self, line: int, existing: str, patch: str, description: str
    ) -> None:
        """Add a conflict description"""
        self.conflicts.append(
            {
                "line": line,
                "existing": existing,
                "patch": patch,
                "description": description,
            }
        )


class GitPatchGenerator:
    """Git patch generator class with enhanced features"""

    def __init__(self, context_lines: int = 3):
        self.context_lines = max(0, context_lines)

    def generate_patch(
        self, file_path: str, changes: List[Dict[str, Union[int, str]]]
    ) -> str:
        """Generate git patch from changes"""
        try:
            if not file_path:
                raise GitPatchError("File path cannot be empty")

            # 读取原始文件内容
            with open(file_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            # 对变更按行号排序
            changes = sorted(changes, key=lambda x: x["line"])

            # 生成补丁头部
            patch_lines = self._generate_header(file_path)
            current_hunk = []
            hunk_stats = {
                "old_start": 0,
                "old_lines": 0,
                "new_start": 0,
                "new_lines": 0,
            }

            def flush_hunk():
                """将当前hunk写入补丁"""
                if current_hunk:
                    header = f"@@ -{hunk_stats['old_start']},{hunk_stats['old_lines']} +{hunk_stats['new_start']},{hunk_stats['new_lines']} @@\n"
                    patch_lines.append(header)
                    patch_lines.extend(current_hunk)
                    current_hunk.clear()
                    hunk_stats.update({"old_lines": 0, "new_lines": 0})

            def add_context_lines(start: int, end: int):
                """添加上下文行"""
                for i in range(start, min(end, len(original_lines))):
                    current_hunk.append(f" {original_lines[i]}")  # 添加原有行
                    hunk_stats["old_lines"] += 1
                    hunk_stats["new_lines"] += 1

            for i, change in enumerate(changes):
                current_line = change["line"] - 1  # 转换为0基索引

                # 确定hunk起始位置
                if not current_hunk:
                    start = max(0, current_line - self.context_lines)
                    hunk_stats["old_start"] = start + 1
                    hunk_stats["new_start"] = start + 1
                    add_context_lines(start, current_line)

                # 处理变更
                if change["type"] == "modify":
                    old_content = change.get("old", "").splitlines(True)
                    new_content = change.get("new", "").splitlines(True)

                    for line in old_content:
                        current_hunk.append(f"-{line}")
                        hunk_stats["old_lines"] += 1

                    for line in new_content:
                        current_hunk.append(f"+{line}")
                        hunk_stats["new_lines"] += 1

                elif change["type"] == "add":
                    # 在添加新行时,确保保留当前行
                    if current_line < len(original_lines):
                        current_hunk.append(
                            f" {original_lines[current_line]}"
                        )  # 保留原有行
                        hunk_stats["old_lines"] += 1
                        hunk_stats["new_lines"] += 1

                    new_content = change.get("new", "").splitlines(True)
                    for line in new_content:
                        current_hunk.append(f"+{line}")
                        hunk_stats["new_lines"] += 1

                elif change["type"] == "delete":
                    old_content = change.get("old", "").splitlines(True)
                    for line in old_content:
                        current_hunk.append(f"-{line}")
                        hunk_stats["old_lines"] += 1

                # 添加后续上下文行
                next_change_line = (
                    changes[i + 1]["line"] - 1
                    if i < len(changes) - 1
                    else len(original_lines)
                )
                context_end = min(
                    current_line + self.context_lines + 1, next_change_line
                )
                add_context_lines(current_line + 1, context_end)

                # 如果与下一个变更距离过远，结束当前hunk
                if (
                    i < len(changes) - 1
                    and changes[i + 1]["line"] - current_line
                    > 2 * self.context_lines + 1
                ):
                    flush_hunk()

            # 处理最后一个hunk
            flush_hunk()
            for i, p in enumerate(patch_lines):
                if p.endswith("\n") and i != len(patch_lines):
                    patch_lines[i] = p[:-1]
            return "\n".join(patch_lines)

        except Exception as e:
            raise GitPatchError(f"Failed to generate patch: {str(e)}")

    def verify_patch(
        self, patch_content: str, file_path: str
    ) -> Tuple[VerificationResult, str]:
        """Verify if patch can be applied cleanly"""
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Parse patch
            hunks = self._parse_patch(patch_content)

            # Check each hunk
            for hunk in hunks:
                # Verify context
                start_idx = hunk.start_line - 1
                if not self._verify_context(lines, start_idx, hunk.content):
                    return (
                        VerificationResult.CONTEXT_MISMATCH,
                        f"Context mismatch at line {hunk.start_line}",
                    )

                # Check for conflicts
                conflicts = self._detect_conflicts(lines, start_idx, hunk)
                if conflicts:
                    return (
                        VerificationResult.CONFLICT,
                        f"Conflicts detected: {conflicts}",
                    )

            return (VerificationResult.VALID, "Patch can be applied cleanly")

        except Exception as e:
            return (
                VerificationResult.INVALID_FORMAT,
                f"Invalid patch format: {str(e)}",
            )

    def preview_patch(self, patch_content: str, file_path: str) -> PatchPreview:
        """Generate preview of patch application"""
        # Read original content
        with open(file_path, "r", encoding="utf-8") as f:
            original_lines = f.readlines()

        # Create working copy of lines
        patched_lines = original_lines.copy()

        # Parse patch
        hunks = self._parse_patch(patch_content)

        # Initialize statistics
        stats = PatchStatistics()
        changes = []
        conflicts = []
        offset = 0

        # Process each hunk
        for hunk in hunks:
            start_idx = hunk.start_line - 1 + offset

            # Check for conflicts
            hunk_conflicts = self._detect_conflicts(patched_lines, start_idx, hunk)
            if hunk_conflicts:
                conflicts.extend(hunk_conflicts)
                stats.conflicts += len(hunk_conflicts)
                continue

            # Track changes
            hunk_changes = self._track_changes(patched_lines, start_idx, hunk)
            changes.extend(hunk_changes)

            # Update statistics
            for change in hunk_changes:
                stats.total_changes += 1
                if "Added" in change["description"]:
                    stats.additions += 1
                elif "Removed" in change["description"]:
                    stats.deletions += 1
                else:
                    stats.modifications += 1

            # Apply changes to preview
            new_lines = []
            for line in hunk.content:
                if line.startswith("+"):
                    new_lines.append(line[1:])
                elif line.startswith("-"):
                    continue
                else:  # Context line
                    new_lines.append(line[1:])

            # Update lines and offset
            patched_lines[start_idx : start_idx + hunk.old_count] = new_lines
            offset += hunk.new_count - hunk.old_count

        return PatchPreview(
            original_lines=original_lines,
            patched_lines=patched_lines,
            changes=changes,
            conflicts=conflicts,
            statistics=stats,
        )

    def apply_patch_safely(
        self,
        patch_content: str,
        source_file: str,
        target_file: str = None,
        force: bool = False,
    ) -> str:
        """安全地应用补丁，增加错误处理和状态跟踪"""
        # 创建临时文件用于存储结果
        temp_dir = tempfile.mkdtemp()
        source_name = os.path.basename(source_file)
        temp_file = os.path.join(temp_dir, f"{source_name}.tmp")

        # 复制源文件到临时文件
        shutil.copy2(source_file, temp_file)

        # 读取源文件
        with open(temp_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 验证补丁
        if not force:
            result, message = self.verify_patch(patch_content, temp_file)
            if result != VerificationResult.VALID:
                shutil.rmtree(temp_dir)
                raise PatchConflictError(
                    f"Patch verification failed: {message}\nUse force=True to apply patch despite conflicts"
                )

        # 解析并应用补丁
        hunks = self._parse_patch(patch_content)
        modified_lines = []
        current_idx = 0

        for hunk in hunks:
            try:
                start_idx = hunk.start_line - 1

                # 添加补丁前的未修改行
                modified_lines.extend(lines[current_idx:start_idx])

                # 应用补丁内容
                for line in hunk.content:
                    if line.startswith("+"):
                        modified_lines.append("\n" + line[1:])  # 添加新行
                    elif line.startswith(" "):
                        if len(modified_lines) == start_idx:
                            modified_lines.append(line[1:])  # 保持上下文行
                        else:
                            modified_lines.append("\n" + line[1:])  # 保持上下文行
                        current_idx = start_idx + 1  # 更新当前索引

                # 跳过被删除的行
                current_idx = start_idx + hunk.old_count

            except Exception as e:
                logger.error(
                    f"Failed to apply hunk starting at line {hunk.start_line}: {str(e)}"
                )
                if not force:
                    shutil.rmtree(temp_dir)
                    raise

        # 添加剩余未修改的行
        modified_lines.extend(lines[current_idx:])

        # 写入修改后的内容
        final_target = (
            target_file
            if target_file
            else os.path.join(temp_dir, f"{source_name}.patched")
        )
        with open(final_target, "w", encoding="utf-8") as f:
            f.writelines(modified_lines)

        # 如果成功，清理临时文件
        if os.path.dirname(final_target) != temp_dir:
            shutil.rmtree(temp_dir)

        return final_target

    def _generate_header(self, file_path: str) -> List[str]:
        """Generate git patch header"""
        import pytz

        timestamp = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S +0000")
        mode = "100644"  # Default mode for regular files

        return [
            f"diff --git a/{file_path} b/{file_path}",
            f"index 0000000..0000000 {mode}",
            f"--- a/{file_path}",
            f"+++ b/{file_path}",
        ]

    def _parse_patch(self, patch_content: str) -> List[PatchHunk]:
        """Parse patch content into hunks"""
        hunks = []
        current_hunk = None
        current_content = []

        for line in patch_content.splitlines():
            if line.startswith("@@"):
                # Save previous hunk if exists
                if current_hunk is not None:
                    hunks.append(
                        PatchHunk(
                            current_hunk[0],
                            current_hunk[1],
                            current_hunk[2],
                            current_content,
                        )
                    )

                # Start new hunk
                old_start, old_count, new_count = PatchHunk.parse_header(line)
                current_hunk = (old_start, old_count, new_count)
                current_content = []
            elif current_hunk is not None and line.startswith(("+", "-", " ")):
                current_content.append(line)

        # Add last hunk
        if current_hunk is not None:
            hunks.append(
                PatchHunk(
                    current_hunk[0], current_hunk[1], current_hunk[2], current_content
                )
            )

        return hunks

    def _verify_context(
        self, lines: List[str], start_idx: int, hunk_content: List[str]
    ) -> bool:
        """验证补丁上下文是否匹配"""
        try:
            file_idx = start_idx

            # 改进：预处理文件行，统一处理换行符
            file_lines = [line.rstrip("\n") for line in lines]

            for line in hunk_content:
                if line.startswith(" "):  # 上下文行
                    if file_idx >= len(file_lines):
                        logger.debug(
                            f"Context verification failed: unexpected EOF at line {file_idx + 1}"
                        )
                        return False

                    hunk_line = line[1:].rstrip("\n")  # 去除前导空格和换行符
                    file_line = file_lines[file_idx]

                    if hunk_line != file_line:
                        logger.debug(f"Context mismatch at line {file_idx + 1}:")
                        logger.debug(f"Expected: '{hunk_line}'")
                        logger.debug(f"Found   : '{file_line}'")
                        return False

                    file_idx += 1
                elif line.startswith("-"):
                    file_idx += 1
                # 对于 '+' 行不增加 file_idx

            return True

        except Exception as e:
            logger.error(f"Error in context verification: {str(e)}", exc_info=True)
            return False

    def _calculate_line_numbers(
        self, changes: List[Dict[str, Union[int, str]]]
    ) -> Dict[str, int]:
        """计算补丁应用后的行号变化"""
        line_changes = defaultdict(int)

        for change in changes:
            line_num = change["line"]
            if change["type"] == "add":
                new_lines = len(change.get("new", "").splitlines())
                line_changes[line_num] += new_lines
            elif change["type"] == "delete":
                old_lines = len(change.get("old", "").splitlines())
                line_changes[line_num] -= old_lines
            elif change["type"] == "modify":
                old_lines = len(change.get("old", "").splitlines())
                new_lines = len(change.get("new", "").splitlines())
                line_changes[line_num] += new_lines - old_lines

        return dict(line_changes)

    def _detect_conflicts(
        self, lines: List[str], start_idx: int, hunk: PatchHunk
    ) -> List[Dict[str, str]]:
        """改进的冲突检测逻辑"""
        conflicts = []
        file_idx = start_idx
        line_number = start_idx + 1

        for line in hunk.content:
            if file_idx >= len(lines):
                if not line.startswith("+"):  # 只有添加行允许超出文件末尾
                    conflicts.append(
                        {
                            "line": line_number,
                            "existing": "<end of file>",
                            "patch": line[1:].rstrip("\n"),
                            "description": "Unexpected end of file",
                        }
                    )
                continue

            if line.startswith((" ", "-")):
                file_line = lines[file_idx].rstrip("\n")
                hunk_line = line[1:].rstrip("\n")

                if file_line != hunk_line:
                    conflicts.append(
                        {
                            "line": line_number,
                            "existing": file_line,
                            "patch": hunk_line,
                            "description": "Content mismatch",
                        }
                    )

                file_idx += 1
                if not line.startswith("-"):  # 不为删除行增加行号
                    line_number += 1
            else:  # 添加行
                line_number += 1

        return conflicts

    def _track_changes(
        self, lines: List[str], start_idx: int, hunk: PatchHunk
    ) -> List[Dict[str, str]]:
        changes = []
        file_idx = start_idx
        actual_line = start_idx + 1

        for line in hunk.content:
            if line.startswith("+"):
                content = line[1:].rstrip("\n")
                changes.append(
                    {
                        "description": f"Added line {actual_line}: {content}",
                        "line": actual_line,
                        "content": content,
                        "type": "add",
                    }
                )
                actual_line += 1
            elif line.startswith("-"):
                content = line[1:].rstrip("\n")
                changes.append(
                    {
                        "description": f"Removed line {actual_line}: {content}",
                        "line": actual_line,
                        "content": content,
                        "type": "delete",
                    }
                )
            else:  # Context line
                actual_line += 1

        return changes


def generate_and_apply_patch_safely(
    source_file: str,
    changes: List[Dict[str, Union[int, str]]],
    target_file: str = None,
    context_lines: int = 3,
    force: bool = False,
    preview: bool = True,
) -> Tuple[str, Optional[PatchPreview]]:
    """
    Convenience function to generate and safely apply patch

    Args:
        source_file: Path to source file
        changes: List of changes
        target_file: Path to target file (optional)
        context_lines: Number of context lines
        force: Whether to force apply despite conflicts
        preview: Whether to return preview information

    Returns:
        Tuple[str, Optional[PatchPreview]]: Path to patched file and preview if requested
    """
    """改进的主函数，增加错误处理和日志"""
    try:
        logger.info(f"Generating patch for {source_file} with {len(changes)} changes")
        generator = GitPatchGenerator(context_lines=context_lines)

        # 生成补丁
        patch = generator.generate_patch(source_file, changes)
        logger.debug(f"Generated patch content:\n{patch}")

        # 验证补丁
        result, message = generator.verify_patch(patch, source_file)
        logger.info(f"Patch verification result: {result.value} - {message}")

        # 生成预览
        patch_preview = None
        if preview:
            patch_preview = generator.preview_patch(patch, source_file)
            logger.debug("Generated patch preview")

        # 应用补丁
        result_file = generator.apply_patch_safely(
            patch, source_file, target_file, force=force
        )
        logger.info(f"Successfully applied patch to {result_file}")

        return result_file, patch_preview

    except Exception as e:
        logger.error(f"Failed to process patch: {str(e)}", exc_info=True)
        raise


def create_test_file(content: str, file_path: str):
    """Create a test file with given content"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def test_basic_patch():
    """Test basic patch generation and application"""
    print("\n=== Testing Basic Patch ===")

    # 确保测试文件内容末尾有换行符
    source_content = """Line 1
Line 2
Line 3
Line 4
Line 5
"""
    source_file = "test_source.txt"
    create_test_file(source_content, source_file)

    changes = [
        {
            "line": 2,
            "old": "Line 2\n",  # 确保包含换行符
            "new": "Modified Line 2\n",
            "type": "modify",
        },
        {"line": 3, "new": "New Line\n", "type": "add"},
    ]

    try:
        logger.info("Generating and applying test patch")
        result_file, preview = generate_and_apply_patch_safely(
            source_file, changes, target_file="test_result.txt", preview=True
        )

        print("\nPatch Preview:")
        print(preview.get_preview())

        with open(result_file, "r") as f:
            print("\nFinal content:")
            print(f.read())

    except GitPatchError as e:
        logger.error(f"Test failed: {e}")
        print(f"Error: {e}")
    finally:
        # 清理测试文件
        for file in [source_file, "test_result.txt"]:
            if os.path.exists(file):
                os.remove(file)


def test_multiline_changes():
    """Test handling of multiline changes"""
    print("\n=== Testing Multiline Changes ===")

    source_content = """def old_function():
    pass
    
tools = [
    create_empty_file,
]"""

    source_file = "test_source.txt"
    create_test_file(source_content, source_file)

    # 多行更改测试
    changes = [
        {
            "line": 1,
            "old": "def old_function():",
            "new": '@tool\ndef fibonacci(n: int) -> list:\n    """\n    生成斐波那契数列\n    """\n    if n <= 0:\n        return []\n    elif n == 1:\n        return [0]\n    \n    fib = [0, 1]\n    for i in range(2, n):\n        fib.append(fib[i-1] + fib[i-2])\n    \n    return fib',
            "type": "modify",
        },
        {"line": 2, "old": "    pass", "new": "", "type": "delete"},
    ]

    try:
        result_file, preview = generate_and_apply_patch_safely(
            source_file, changes, preview=True
        )

        print("\nPatch Preview:")
        print(preview.get_preview())

    except GitPatchError as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists(source_file):
            os.remove(source_file)


def test_conflict_handling():
    """Test patch conflict detection and handling"""
    print("\n=== Testing Conflict Handling ===")

    # Create test file with content that will conflict
    source_content = """Line 1
Modified content
Line 3
Line 4
Line 5
"""
    source_file = "test_source.txt"
    create_test_file(source_content, source_file)

    # Define changes that will conflict
    changes = [
        {
            "line": 2,
            "old": "Line 2",  # This doesn't match the actual content
            "new": "Modified Line 2",
            "type": "modify",
        }
    ]

    try:
        # Try to apply patch normally
        result_file, preview = generate_and_apply_patch_safely(
            source_file, changes, preview=True
        )

    except PatchConflictError as e:
        print("\nDetected conflict as expected:")
        print(e)

        # Try force apply
        print("\nTrying with force=True:")
        result_file, preview = generate_and_apply_patch_safely(
            source_file, changes, force=True, preview=True
        )
        print(preview.get_preview())

    finally:
        # Cleanup
        if os.path.exists(source_file):
            os.remove(source_file)


def test_patch_statistics():
    """Test patch statistics generation"""
    print("\n=== Testing Patch Statistics ===")

    # Create test file
    source_content = """Line 1
Line 2
Line 3
Line 4
Line 5
"""
    source_file = "test_source.txt"
    create_test_file(source_content, source_file)

    # Define various types of changes
    changes = [
        {"line": 2, "old": "Line 2", "new": "Modified Line 2", "type": "modify"},
        {"line": 4, "new": "New Line", "old": "", "type": "add"},
        {"line": 5, "old": "Line 5", "new": "", "type": "delete"},
    ]

    try:
        # Generate and apply patch
        result_file, preview = generate_and_apply_patch_safely(
            source_file, changes, preview=True
        )

        # Show statistics
        print("\nPatch Statistics:")
        print(preview.statistics)

        # Show JSON format
        print("\nJSON Preview:")
        print(preview.to_json())

    except GitPatchError as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        if os.path.exists(source_file):
            os.remove(source_file)


def test_complex_patches():
    """测试复杂补丁场景"""
    source_content = """def test_function():
    # Old comment
    print("old code")
    return None
"""

    changes = [
        {
            "line": 2,
            "old": "    # Old comment\n",
            "new": "    # New comment\n    # Additional comment\n",
            "type": "modify",
        },
        {
            "line": 3,
            "old": '    print("old code")\n',
            "new": '    print("new code")\n    print("additional line")\n',
            "type": "modify",
        },
    ]

    source_file = "test_complex.txt"
    create_test_file(source_content, source_file)

    try:
        result_file, preview = generate_and_apply_patch_safely(
            source_file, changes, preview=True
        )
        print("\nComplex patch preview:")
        print(preview.get_preview())
    finally:
        if os.path.exists(source_file):
            os.remove(source_file)


if __name__ == "__main__":
    # Run all tests
    test_basic_patch()
    test_multiline_changes()
    test_complex_patches()
    test_conflict_handling()
    test_patch_statistics()
