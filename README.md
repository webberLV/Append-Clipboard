
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



## Troubleshooting

- Invoke with the full Python path if `python` is not on PATH.
