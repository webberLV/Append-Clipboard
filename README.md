# Clipboard Code Ingest (Windows-only)

A command-line tool that inventories files/folders, filters and orders decodable text,
and emits analysis-ready bundles to the clipboard (Markdown or JSONL).

## Requirements

Windows  
Python 3.x  
Dependencies:
  pip install pyperclip pywin32

## Usage

Paths are space-separated.
Paths containing spaces must be quoted.

Commands (no flags):

  r    Replace clipboard (Markdown)
  a    Append to clipboard (Markdown)
  jr   Replace clipboard (JSONL)
  j    Append to clipboard (JSONL)

Explorer-selection variants (suffix `e`):

  re   ae   jre   je

Explorer variants operate on the current Explorer selection
instead of explicit path arguments.

## Behavior Guarantees

- Full inventory (all discovered files and directories):
  - Printed to stderr
  - Embedded at the top of clipboard output
- Only clipboard content is subject to:
  - Skip rules
  - Text/binary detection
  - Per-file and total size limits
- Deterministic file ordering via priority rules
- Safe encoding detection (UTF-8, UTF-16, Latin-1 fallback)
- JSONL mode:
  - Uses `agents.md` as controller if present
  - Otherwise emits a strict fallback controller
- No invented files
- No implicit globbing or recursion beyond explicit paths

## Notes

- This tool is designed for LLM ingestion and code analysis workflows.
- Output is structured, bounded, and reproducible.

## Troubleshooting

- Invoke with the full Python path if `python` is not on PATH.
- Ensure the script is executed with the same Python installation
  where dependencies were installed.
