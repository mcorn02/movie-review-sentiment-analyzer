#!/usr/bin/env python3
"""
Pre-commit documentation generator.

For each staged Python file, generates/updates a corresponding docs/<module>.md
with an in-depth analysis of the module and what changed in this commit.
If functional changes are detected, also updates README.md.
"""

import os
import subprocess
import sys
from pathlib import Path

import anthropic

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
README_PATH = PROJECT_ROOT / "README.md"

# Python files to skip (not part of the app)
EXCLUDE_PREFIXES = ("venv/", "scripts/")


def get_staged_python_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    files = result.stdout.strip().splitlines()
    return [
        f for f in files
        if f.endswith(".py") and not any(f.startswith(p) for p in EXCLUDE_PREFIXES)
    ]


def get_file_diff(file_path: str) -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", file_path],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return result.stdout.strip()


def read_file(file_path: str) -> str:
    full_path = PROJECT_ROOT / file_path
    if not full_path.exists():
        return ""
    return full_path.read_text()


def read_existing_doc(doc_path: Path) -> str:
    if doc_path.exists():
        return doc_path.read_text()
    return ""


def generate_module_doc(client: anthropic.Anthropic, file_path: str, content: str, diff: str) -> tuple[str, bool]:
    """Returns (markdown_doc, has_functional_changes)."""
    existing_doc = read_existing_doc(DOCS_DIR / (file_path.replace("/", "_").removesuffix(".py") + ".md"))

    has_diff = bool(diff)
    diff_section = f"\n\n## Git diff for this commit\n```diff\n{diff}\n```" if has_diff else ""

    prompt = f"""You are a technical documentation writer for a Python project.

Analyze the following Python module and produce a comprehensive markdown documentation file.

File path: `{file_path}`

### Current file content:
```python
{content}
```
{diff_section}

{"### Existing documentation (update this):" if existing_doc else ""}
{existing_doc if existing_doc else ""}

Write a single markdown document with these sections:
1. **Module Overview** — purpose, responsibilities, where it fits in the system
2. **Key Components** — all public functions, classes, and constants with:
   - Signature
   - What it does
   - Parameters and return values
   - Any side effects or dependencies
3. **What Changed** (only if a diff was provided) — an in-depth explanation of:
   - What was added, modified, or removed
   - Why the change matters functionally
   - Any behavioral differences from before
4. **Dependencies & Integration** — what this module imports from and what depends on it

At the very end, on its own line, write exactly one of:
- `FUNCTIONAL_CHANGE: YES` — if the diff includes changes to public APIs, CLI behavior, configuration defaults, or user-visible functionality
- `FUNCTIONAL_CHANGE: NO` — otherwise (or if no diff)

Be thorough and precise. Use code blocks for signatures."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    doc = message.content[0].text
    has_functional_changes = "FUNCTIONAL_CHANGE: YES" in doc
    # Strip the marker line from the doc
    doc = "\n".join(
        line for line in doc.splitlines()
        if not line.strip().startswith("FUNCTIONAL_CHANGE:")
    ).rstrip()

    return doc, has_functional_changes


def update_readme(client: anthropic.Anthropic, readme: str, change_summaries: list[str]) -> str:
    """Returns updated README content."""
    changes_text = "\n\n".join(change_summaries)

    prompt = f"""You are a technical writer. The following functional changes were made to a Python project.
Update the README to reflect these changes accurately. Only modify sections that are directly affected.
Do not add new sections unless truly necessary. Preserve all formatting, style, and unrelated content exactly.

## Functional changes made:
{changes_text}

## Current README:
{readme}

Return the complete updated README content only, with no preamble or explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def main():
    staged_files = get_staged_python_files()

    if not staged_files:
        print("[docs] No staged Python files — skipping documentation generation.")
        sys.exit(0)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[docs] ANTHROPIC_API_KEY not set — skipping documentation generation.")
        sys.exit(0)

    client = anthropic.Anthropic(api_key=api_key)
    DOCS_DIR.mkdir(exist_ok=True)

    functional_change_summaries = []
    staged_doc_paths = []

    for file_path in staged_files:
        print(f"[docs] Analyzing {file_path}...")
        content = read_file(file_path)
        diff = get_file_diff(file_path)

        try:
            doc, has_functional_changes = generate_module_doc(client, file_path, content, diff)
        except Exception as e:
            print(f"[docs] Warning: failed to generate docs for {file_path}: {e}")
            continue

        # Write to docs/<module_path_with_underscores>.md
        doc_filename = file_path.replace("/", "_").removesuffix(".py") + ".md"
        doc_path = DOCS_DIR / doc_filename
        doc_path.write_text(doc + "\n")
        staged_doc_paths.append(str(doc_path.relative_to(PROJECT_ROOT)))
        print(f"[docs] Written {doc_path.relative_to(PROJECT_ROOT)}")

        if has_functional_changes and diff:
            functional_change_summaries.append(
                f"### `{file_path}`\n{diff[:3000]}"  # cap diff size sent to README updater
            )

    if functional_change_summaries:
        print("[docs] Functional changes detected — updating README.md...")
        readme = README_PATH.read_text()
        try:
            updated_readme = update_readme(client, readme, functional_change_summaries)
            README_PATH.write_text(updated_readme)
            staged_doc_paths.append("README.md")
            print("[docs] README.md updated.")
        except Exception as e:
            print(f"[docs] Warning: failed to update README: {e}")

    # Stage all generated/updated files
    if staged_doc_paths:
        subprocess.run(
            ["git", "add"] + staged_doc_paths,
            cwd=PROJECT_ROOT, check=True
        )
        print(f"[docs] Staged {len(staged_doc_paths)} documentation file(s).")

    print("[docs] Done.")


if __name__ == "__main__":
    main()
