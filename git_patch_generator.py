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
            # Validate file path
            if not file_path:
                raise GitPatchError("File path cannot be empty")

            # Read file if exists
            original_content = ""
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    original_content = f.read()

            # Sort changes by line number
            changes = sorted(changes, key=lambda x: x["line"])

            # Generate patch header
            patch_lines = self._generate_header(file_path)

            # Generate hunks
            current_hunk = []
            hunk_start = None
            old_lines = new_lines = 0
            original_lines = original_content.splitlines()

            for change in changes:
                if not isinstance(change.get("line"), int):
                    raise GitPatchError(f"Invalid line number in change: {change}")

                if hunk_start is None:
                    hunk_start = max(1, change["line"] - self.context_lines)

                # Add context lines
                while len(current_hunk) < change["line"] - hunk_start:
                    line_idx = hunk_start + len(current_hunk) - 1
                    if line_idx < len(original_lines):
                        current_hunk.append(f" {original_lines[line_idx]}")
                        old_lines += 1
                        new_lines += 1

                # 处理代码块更改
                def process_multiline_content(content: str) -> List[str]:
                    """处理多行内容,返回行列表"""
                    if not content:
                        return []
                    return content.split("\n")

                # Add the change
                if change["type"] == "modify":
                    # 处理老内容
                    old_lines_content = process_multiline_content(change["old"])
                    for line in old_lines_content:
                        current_hunk.append(f"-{line}")
                        old_lines += 1

                    # 处理新内容
                    new_lines_content = process_multiline_content(change["new"])
                    for line in new_lines_content:
                        current_hunk.append(f"+{line}")
                        new_lines += 1

                elif change["type"] == "add":
                    new_lines_content = process_multiline_content(change["new"])
                    for line in new_lines_content:
                        current_hunk.append(f"+{line}")
                        new_lines += 1

                elif change["type"] == "delete":
                    old_lines_content = process_multiline_content(change["old"])
                    for line in old_lines_content:
                        current_hunk.append(f"-{line}")
                        old_lines += 1

            # Add final context lines
            if hunk_start is not None and changes:
                last_change = changes[-1]
                last_line = last_change["line"]

                # 对于多行更改,需要计算实际的最后一行
                if last_change.get("new"):
                    last_line += len(process_multiline_content(last_change["new"]))
                elif last_change.get("old"):
                    last_line += len(process_multiline_content(last_change["old"]))

                for i in range(self.context_lines):
                    line_idx = last_line + i
                    if line_idx < len(original_lines):
                        current_hunk.append(f" {original_lines[line_idx]}")
                        old_lines += 1
                        new_lines += 1

            # Add hunk header and content
            if current_hunk:
                hunk_header = (
                    f"@@ -{hunk_start},{old_lines} +{hunk_start},{new_lines} @@"
                )
                patch_lines.append(hunk_header)
                patch_lines.extend(current_hunk)

            return "\n".join(patch_lines) + "\n"

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
        """Safely apply patch with conflict checking"""
        # Verify patch first
        result, message = self.verify_patch(patch_content, source_file)

        if result != VerificationResult.VALID and not force:
            raise PatchConflictError(
                f"Patch verification failed: {message}\n"
                "Use force=True to apply patch despite conflicts"
            )

        # Generate preview
        preview = self.preview_patch(patch_content, source_file)

        # Create target file
        if target_file is None:
            temp_dir = tempfile.mkdtemp()
            source_name = os.path.basename(source_file)
            target_file = os.path.join(temp_dir, f"{source_name}.patched")

        # Write patched content
        with open(target_file, "w", encoding="utf-8") as f:
            f.writelines(preview.patched_lines)

        return target_file

    def _generate_header(self, file_path: str) -> List[str]:
        """Generate git patch header"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S +0000")
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
        """Verify that context lines match the file content"""
        file_idx = start_idx

        for line in hunk_content:
            if line.startswith(" "):  # Context line
                if file_idx >= len(lines) or lines[file_idx].rstrip("\n") != line[
                    1:
                ].rstrip("\n"):
                    return False
                file_idx += 1
            elif line.startswith("-"):  # Removed line
                if file_idx >= len(lines) or lines[file_idx].rstrip("\n") != line[
                    1:
                ].rstrip("\n"):
                    return False
                file_idx += 1
            else:  # Added line
                continue

        return True

    def _detect_conflicts(
        self, lines: List[str], start_idx: int, hunk: PatchHunk
    ) -> List[Dict[str, str]]:
        """Detect conflicts in a hunk"""
        conflicts = []
        file_idx = start_idx

        for i, line in enumerate(hunk.content):
            if line.startswith("-") or line.startswith(" "):  # Line should match
                if file_idx >= len(lines):
                    conflicts.append(
                        {
                            "line": file_idx + 1,
                            "existing": "<end of file>",
                            "patch": line[1:],
                            "description": f"Unexpected end of file at line {file_idx + 1}",
                        }
                    )
                elif lines[file_idx].rstrip("\n") != line[1:].rstrip("\n"):
                    conflicts.append(
                        {
                            "line": file_idx + 1,
                            "existing": lines[file_idx].rstrip("\n"),
                            "patch": line[1:].rstrip("\n"),
                            "description": f"Content mismatch at line {file_idx + 1}",
                        }
                    )
                file_idx += 1

        return conflicts

    def _track_changes(
        self, lines: List[str], start_idx: int, hunk: PatchHunk
    ) -> List[Dict[str, str]]:
        """Track changes made by a hunk"""
        changes = []
        file_idx = start_idx

        for line in hunk.content:
            if line.startswith("+"):
                changes.append(
                    {"description": f"Added line {file_idx + 1}: {line[1:].rstrip()}"}
                )
            elif line.startswith("-"):
                changes.append(
                    {"description": f"Removed line {file_idx + 1}: {line[1:].rstrip()}"}
                )
                file_idx += 1
            else:
                file_idx += 1

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
    generator = GitPatchGenerator(context_lines=context_lines)
    patch = generator.generate_patch(source_file, changes)

    # Generate preview if requested
    patch_preview = None
    if preview:
        patch_preview = generator.preview_patch(patch, source_file)

    # Apply patch
    result_file = generator.apply_patch_safely(
        patch, source_file, target_file, force=force
    )

    return result_file, patch_preview


def create_test_file(content: str, file_path: str):
    """Create a test file with given content"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def test_basic_patch():
    """Test basic patch generation and application"""
    print("\n=== Testing Basic Patch ===")

    # Create test file
    source_content = """Line 1
Line 2
Line 3
Line 4
Line 5
"""
    source_file = "test_source.txt"
    create_test_file(source_content, source_file)

    # Define changes
    changes = [
        {"line": 2, "old": "Line 2", "new": "Modified Line 2", "type": "modify"},
        {"line": 4, "new": "New Line", "old": "", "type": "add"},
    ]

    try:
        # Generate and apply patch with preview
        result_file, preview = generate_and_apply_patch_safely(
            source_file, changes, target_file="test_result.txt", preview=True
        )

        # Show preview
        print("\nPatch Preview:")
        print(preview.get_preview())

        print(f"\nPatch applied successfully to: {result_file}")

        # Show final content
        print("\nFinal content:")
        with open(result_file, "r") as f:
            print(f.read())

    except GitPatchError as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
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
            "old": "def old_function():\n    pass",
            "new": '@tool\ndef fibonacci(n: int) -> list:\n    """\n    生成斐波那契数列\n    """\n    if n <= 0:\n        return []\n    elif n == 1:\n        return [0]\n    \n    fib = [0, 1]\n    for i in range(2, n):\n        fib.append(fib[i-1] + fib[i-2])\n    \n    return fib',
            "type": "modify",
        }
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


if __name__ == "__main__":
    # Run all tests
    test_basic_patch()
    test_multiline_changes()
    test_conflict_handling()
    test_patch_statistics()
