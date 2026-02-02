# Windows-only. Requires:
#   pip install pyperclip pywin32
#
# Commands (NO FLAGS):
#   r   replace clipboard (markdown)
#   a   append clipboard (markdown)
#   jr  replace clipboard (jsonl)
#   j   append clipboard (jsonl)
#
# Explorer-selection variants (suffix 'e'):
#   re  ae  jre  je
#
# Behavior:
# - Inventory is BOTH printed to stderr AND embedded into clipboard output at top.
# - Then applies skip/text/size rules only for what gets copied to clipboard.
# - Preserves: prompt header generation, JSONL controller behavior (agents.md), include_prompt rules,
#   file priority ordering, skip rules, encoding detection.



# Troubleshooting: Ensure that python full path is used and full path to the python script downlaoded  (python in a virtual enviroment won't use your windows system and user variables).
