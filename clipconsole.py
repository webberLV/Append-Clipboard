#!/usr/bin/env python3
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

import os
import sys
import argparse
import json
import pyperclip

import pythoncom  # pywin32
import win32com.client  # pywin32

if os.name != "nt":
    print("This script is Windows-only.", file=sys.stderr)
    sys.exit(1)

# ---------------- Config ----------------
MAX_TOTAL_BYTES = 20 * 1024 * 1024   # 20 MB clipboard guard (JSONL body + controller + inventory)
MAX_FILE_BYTES  = 2 * 1024 * 1024    # 2 MB per-file guard

INLINE_PATH_COMMENTS = True
USE_ABSOLUTE_PATHS = True

# Inventory behavior
INVENTORY_TO_STDERR = True
INVENTORY_TO_CLIPBOARD = True

# lowercase only
SKIP_DIRS = {
    "_locales",
    ".git",
    "node_modules",
    "dist",
    "build",
    "out",
    ".next",
    ".cache",
    "venv",
    ".venv",
    "__pycache__",
}

SKIP_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp4", ".avi", ".mov", ".wmv", ".mp3", ".wav",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".doc", ".docx",
    ".bak",
    ".map",
    ".json",     # all JSON (except allowlist below)
    ".log",
    ".tmp",
}

SKIP_FILENAMES = set()

ALLOW_FILENAMES = {
    "manifest.json",
    "package.json",
}

CONTROLLER_FILENAMES = {
    "agents.md",
}

CMD_MAP = {
    "r":   ("r",  False),
    "a":   ("a",  False),
    "jr":  ("jr", False),
    "j":   ("j",  False),
    "re":  ("r",  True),
    "ae":  ("a",  True),
    "jre": ("jr", True),
    "je":  ("j",  True),
}


def get_explorer_selected_paths():
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        wins = shell.Windows()

        out = []
        for i in range(wins.Count):
            w = wins.Item(i)
            try:
                full = str(getattr(w, "FullName", "")).lower()
                if not full.endswith("\\explorer.exe"):
                    continue

                doc = getattr(w, "Document", None)
                if doc is None:
                    continue

                items = doc.SelectedItems()
                if items is None or items.Count <= 0:
                    continue

                for j in range(items.Count):
                    it = items.Item(j)
                    p = str(getattr(it, "Path", "")).strip()
                    if p:
                        out.append(p)

                if out:
                    break
            except Exception:
                continue

        return out
    finally:
        pythoncom.CoUninitialize()


def _is_minified_name(filename_lower: str) -> bool:
    return (
        filename_lower.endswith(".min.js")
        or filename_lower.endswith(".min.css")
        or filename_lower.endswith(".min.html")
    )


def should_skip_file(path: str) -> bool:
    filename = os.path.basename(path).lower()
    _, ext = os.path.splitext(filename)

    if filename in ALLOW_FILENAMES:
        return False

    if filename in SKIP_FILENAMES:
        return True
    if ext in SKIP_EXTENSIONS:
        return True
    if _is_minified_name(filename):
        return True

    return False


def _looks_like_utf16_without_bom(b: bytes) -> str | None:
    if not b:
        return None

    nul_ratio = b.count(b"\x00") / len(b)
    if nul_ratio < 0.20:
        return None

    even = b[0::2]
    odd = b[1::2]
    if not even or not odd:
        return None

    even_nul = even.count(b"\x00") / len(even)
    odd_nul = odd.count(b"\x00") / len(odd)

    if odd_nul > 0.60 and even_nul < 0.30:
        return "utf-16-le"
    if even_nul > 0.60 and odd_nul < 0.30:
        return "utf-16-be"

    return None


def is_probably_text(path: str, sample_size: int = 8192) -> bool:
    try:
        with open(path, "rb") as f:
            b = f.read(sample_size)
        if not b:
            return True

        if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
            return True

        if _looks_like_utf16_without_bom(b) is not None:
            return True

        null_ratio = b.count(b"\x00") / max(1, len(b))
        if null_ratio > 0.20:
            return False

        bad = 0
        for c in b:
            if c < 9 or (13 < c < 32) or c == 127:
                bad += 1
        return (bad / len(b)) < 0.20
    except Exception:
        return False


def detect_file_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".json": "json",
        ".html": "html",
        ".css": "css",
        ".ini": "Initialization_file",
        ".csv": "Comma-Separated Values",
        ".py": "python",
        ".ahk": "autohotkey",
        ".bat": "batch",
        ".ps1": "powershell",
        ".reg": "registry",
        ".txt": "text",
        ".md": "markdown",
    }.get(ext, "text")


def comment_prefix_for_type(ft: str) -> tuple[str, str] | None:
    if ft in ("javascript", "typescript", "batch", "powershell", "registry"):
        return ("// ", "")
    if ft in ("python", "text", "markdown"):
        return ("# ", "")
    if ft == "css":
        return ("/* ", " */")
    if ft == "html":
        return ("<!-- ", " -->")
    return None


def display_path(path: str) -> str:
    if USE_ABSOLUTE_PATHS:
        return os.path.abspath(path).replace("\\", "/")
    return path.replace("\\", "/")


def get_file_priority(path: str):
    filename = os.path.basename(path).lower()

    priority_map = {
        "agents.md": 0,

        "manifest.json": 1,
        "manifest-c.json": 2,
        "manifest-f.json": 3,
        "package.json": 4,

        "service-worker.js": 10,
        "background.js": 11,
        "worker.js": 12,
        "messagelistener.js": 13,
        "scriptimport.js": 14,

        "helper.js": 20,
        "urlutils.js": 21,
        "tabsinfo.js": 22,

        "content.js": 30,
        "content-script.js": 31,

        "popup.html": 40,
        "popup.js": 41,
        "popup.css": 42,
        "list.html": 43,
        "list.js": 44,

        "options.html": 50,
        "options.js": 51,
        "options.css": 52,

        "badge.js": 60,

        "readme.md": 800,
        "license": 810,
    }

    if filename in priority_map:
        return (priority_map[filename], path)

    ext = os.path.splitext(filename)[1].lower()
    return ({
        ".json": 200,
        ".js": 210,
        ".mjs": 210,
        ".cjs": 210,
        ".ts": 215,
        ".tsx": 215,
        ".html": 300,
        ".css": 400,
        ".py": 500,
        ".ps1": 510,
        ".bat": 520,
        ".md": 800,
        ".txt": 900,
    }.get(ext, 999), path)


def _looks_like_chrome_extension(file_paths) -> bool:
    for p in file_paths:
        if os.path.basename(p).lower() == "manifest.json":
            return True
    return False


def generate_analysis_prompt(file_count, file_types, is_extension: bool, output_format: str):
    header = "# Chrome Extension Code Review\n" if is_extension else "# Codebase Review\n"

    s = header + "\n"
    s += "## Input Summary\n"
    s += f"- Total files pasted: {file_count}\n"
    s += "- File type counts: " + ", ".join(f"{k}({v})" for k, v in file_types.items()) + "\n\n"

    s += "## Output Requirements\n"
    s += "1) Highest-impact correctness bugs first (cite FILE + exact code).\n"
    s += "2) Root cause, user-visible symptom, minimal safe fix.\n"
    s += "3) Performance risks.\n"
    s += "4) Security / robustness issues.\n"
    s += "5) Concrete patches (diffs or full files).\n"
    s += "6) No invented files.\n\n"

    if is_extension:
        s += "## Chrome Extension Specific Checks\n"
        s += "- MV3 manifest correctness.\n"
        s += "- Background lifecycle.\n"
        s += "- Message passing.\n"
        s += "- Tabs/windows hygiene.\n"
        s += "- Cleanup.\n\n"
    else:
        s += "## General Codebase Checks\n"
        s += "- Async sequencing.\n"
        s += "- Resource cleanup.\n"
        s += "- Error handling.\n\n"

    if output_format == "jsonl":
        s += "## Format\n"
        s += "Each subsequent line is a JSON object with fields: path, type, content.\n"
        s += "Use content as the exact file text (newlines preserved via JSON escapes).\n\n"

    s += "---\n\n## Pasted Files\n"
    s += "(Each file begins with a FILE: path comment.)\n\n"
    return s


def _decode_bytes(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        try:
            text = raw.decode("utf-16")
        except Exception:
            return None
    else:
        enc = _looks_like_utf16_without_bom(raw[:8192])
        if enc:
            try:
                text = raw.decode(enc)
            except Exception:
                return None
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    text = raw.decode("latin-1")
                except Exception:
                    return None

    if not text:
        return ""

    repl_ratio = text.count("\ufffd") / max(1, len(text))
    ctrl = sum(
        1 for ch in text
        if ((ord(ch) < 32 and ch not in ("\t", "\n", "\r")) or ord(ch) == 127)
    )
    ctrl_ratio = ctrl / max(1, len(text))

    if repl_ratio > 0.02 or ctrl_ratio > 0.20:
        return None

    return text


def _inventory_comment_block(inventory_text: str, output_format: str) -> str:
    """
    Put inventory inside clipboard in a safe way:
    - markdown: plain lines
    - jsonl: comment lines starting with "# " (so it's a controller/header outside JSONL records)
    """
    if not inventory_text:
        return ""

    if output_format == "jsonl":
        lines = inventory_text.splitlines()
        return "".join("# " + line + "\n" for line in lines) + "\n"

    # markdown
    return inventory_text + ("\n" if not inventory_text.endswith("\n") else "") + "\n"


def list_all_entries(folder_path: str):
    all_dirs: list[str] = []
    all_files: list[str] = []
    for root, dirs, files in os.walk(folder_path):
        root_abs = os.path.abspath(root)
        for d in dirs:
            all_dirs.append(os.path.abspath(os.path.join(root_abs, d)))
        for f in files:
            all_files.append(os.path.abspath(os.path.join(root_abs, f)))
    return all_dirs, all_files


def collect_files_and_inventory(paths):
    """
    Returns (filtered_files, inventory_text).
    Inventory lists everything discovered (dirs+files) with absolute paths.
    """
    discovered_files: list[str] = []
    inv_lines: list[str] = []

    for p in paths:
        if not os.path.exists(p):
            msg = f"Path not found: {p}"
            if INVENTORY_TO_STDERR:
                print(msg, file=sys.stderr)
            inv_lines.append(msg)
            continue

        p_abs = os.path.abspath(p)
        inv_lines.append(f"== INVENTORY: {p_abs} ==")
        if INVENTORY_TO_STDERR:
            print(f"== INVENTORY: {p_abs} ==", file=sys.stderr)

        if os.path.isfile(p_abs):
            inv_lines.append(f"FILE {p_abs}")
            if INVENTORY_TO_STDERR:
                print(f"FILE {p_abs}", file=sys.stderr)
            discovered_files.append(p_abs)
            continue

        if os.path.isdir(p_abs):
            dirs, files = list_all_entries(p_abs)

            for d in sorted(dirs, key=lambda s: s.lower()):
                inv_lines.append(f"DIR  {d}")
                if INVENTORY_TO_STDERR:
                    print(f"DIR  {d}", file=sys.stderr)

            for f in sorted(files, key=lambda s: s.lower()):
                inv_lines.append(f"FILE {f}")
                if INVENTORY_TO_STDERR:
                    print(f"FILE {f}", file=sys.stderr)

            discovered_files.extend(files)
            continue

        msg = f"Unsupported path: {p}"
        inv_lines.append(msg)
        if INVENTORY_TO_STDERR:
            print(msg, file=sys.stderr)

    # dedupe, then priority sort
    seen = set()
    deduped: list[str] = []
    for p in discovered_files:
        rp = os.path.normcase(os.path.abspath(p))
        if rp in seen:
            continue
        seen.add(rp)
        deduped.append(p)

    deduped.sort(key=get_file_priority)

    # filter
    filtered: list[str] = []
    for p in deduped:
        try:
            if should_skip_file(p):
                continue
            if not is_probably_text(p):
                continue
            filtered.append(p)
        except Exception:
            continue

    inventory_text = "\n".join(inv_lines).rstrip() + "\n"
    return filtered, inventory_text


def read_files_as_text(file_paths, output_format="markdown", include_prompt=True, inventory_text=""):
    out = []
    jsonl_lines = []
    file_types = {}
    total_bytes = 0
    count = 0
    truncated = False

    is_ext = _looks_like_chrome_extension(file_paths)

    controller_text = ""
    controller_path = None

    # Inventory goes first in clipboard (if enabled)
    inv_block = ""
    if INVENTORY_TO_CLIPBOARD:
        inv_block = _inventory_comment_block(inventory_text, output_format=output_format)
        inv_bytes = len(inv_block.encode("utf-8", errors="replace"))
        total_bytes += inv_bytes
        if total_bytes > MAX_TOTAL_BYTES:
            return inv_block[:0], 0, True

    if output_format == "jsonl" and include_prompt:
        # Find agents.md as controller
        for p in file_paths:
            if os.path.basename(p).lower() in CONTROLLER_FILENAMES:
                controller_path = p
                break

        if controller_path:
            try:
                raw = open(controller_path, "rb").read()
                text = _decode_bytes(raw)
                if text is None:
                    text = ""

                disp = display_path(controller_path)
                ft = detect_file_type(controller_path)
                if INLINE_PATH_COMMENTS:
                    c = comment_prefix_for_type(ft)
                    if c is not None:
                        prefix, suffix = c
                        text = f"{prefix}FILE: {disp}{suffix}\n{text}"
                    else:
                        text = f"# FILE: {disp}\n{text}"

                controller_text = text.rstrip() + "\n\n"
            except Exception:
                controller_text = ""
        else:
            lines = []
            lines.append("# Controller")
            lines.append("# If AGENTS.MD is present, it is authoritative and overrides this fallback.")
            lines.append("#")
            lines.append("# Output requirements:")
            lines.append("# 1) Highest-impact correctness bugs first (cite FILE + exact code).")
            lines.append("# 2) Root cause, user-visible symptom, minimal safe fix.")
            lines.append("# 3) Performance risks.")
            lines.append("# 4) Security / robustness issues.")
            lines.append("# 5) Concrete patches (diffs or full files).")
            lines.append("# 6) No invented files.")
            if is_ext:
                lines.append("#")
                lines.append("# Chrome Extension checks (MV3): manifest, background lifecycle, message passing, tabs/windows hygiene, cleanup.")
            lines.append("#")
            lines.append("# Format:")
            lines.append("# JSONL records follow with fields: {path, type, content}.")
            lines.append("# Do not treat this controller as a file; JSONL records start below.")
            controller_text = "\n".join(lines).rstrip() + "\n\n"

        cb = len(controller_text.encode("utf-8", errors="replace"))
        if total_bytes + cb > MAX_TOTAL_BYTES:
            return inv_block[:0], 0, True
        total_bytes += cb

    for p in file_paths:
        # In JSONL mode, do not emit the controller file as a JSONL record.
        if output_format == "jsonl" and controller_path:
            try:
                if os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(controller_path)):
                    continue
            except Exception:
                pass

        try:
            st = os.stat(p)
            if st.st_size > MAX_FILE_BYTES:
                continue
        except Exception:
            continue

        try:
            raw = open(p, "rb").read()
        except Exception:
            continue

        text = _decode_bytes(raw)
        if text is None:
            continue

        disp = display_path(p)
        ft = detect_file_type(p)
        file_types[ft] = file_types.get(ft, 0) + 1

        if INLINE_PATH_COMMENTS:
            c = comment_prefix_for_type(ft)
            if c is not None:
                prefix, suffix = c
                text = f"{prefix}FILE: {disp}{suffix}\n{text}"
            else:
                text = f"# FILE: {disp}\n{text}"

        if output_format == "jsonl":
            line = json.dumps({"path": disp, "type": ft, "content": text}, ensure_ascii=False) + "\n"
            bsz = len(line.encode("utf-8", errors="replace"))
            if total_bytes + bsz > MAX_TOTAL_BYTES:
                truncated = True
                break
            jsonl_lines.append(line)
            total_bytes += bsz
            count += 1
            continue

        block = text
        if not block.endswith("\n"):
            block += "\n"
        block += "\n"

        bsz = len(block.encode("utf-8", errors="replace"))
        if total_bytes + bsz > MAX_TOTAL_BYTES:
            truncated = True
            break

        out.append(block)
        total_bytes += bsz
        count += 1

    if output_format == "jsonl":
        body = "".join(jsonl_lines)
        if not include_prompt:
            return inv_block + body, count, truncated
        return inv_block + controller_text + body, count, truncated

    prompt = generate_analysis_prompt(count, file_types, is_ext, output_format) if include_prompt else ""
    return inv_block + prompt + "".join(out), count, truncated


def replace_clipboard(paths, output_format="markdown"):
    files, inventory_text = collect_files_and_inventory(paths)
    if not files:
        print("No valid files found", file=sys.stderr)
        # still allow inventory-only clipboard if asked
        if INVENTORY_TO_CLIPBOARD and inventory_text:
            inv_block = _inventory_comment_block(inventory_text, output_format=output_format)
            pyperclip.copy(inv_block)
        return 1

    content, count, truncated = read_files_as_text(
        files,
        output_format=output_format,
        include_prompt=True,
        inventory_text=inventory_text,
    )

    if count == 0:
        print("No decodable text files found", file=sys.stderr)
        if INVENTORY_TO_CLIPBOARD and inventory_text:
            inv_block = _inventory_comment_block(inventory_text, output_format=output_format)
            pyperclip.copy(inv_block)
        return 1

    pyperclip.copy(content)

    msg = f"Replaced clipboard: {count} files"
    if truncated:
        msg += " (TRUNCATED)"
    print(msg, file=sys.stderr)
    return 0


def append_clipboard(paths, output_format="markdown"):
    files, inventory_text = collect_files_and_inventory(paths)
    if not files:
        print("No valid files found", file=sys.stderr)
        if INVENTORY_TO_CLIPBOARD and inventory_text:
            inv_block = _inventory_comment_block(inventory_text, output_format=output_format)
            existing = pyperclip.paste()
            sep = "" if (not existing or existing.endswith("\n")) else "\n"
            pyperclip.copy(existing + sep + inv_block)
        return 1

    existing = pyperclip.paste()

    include_prompt = True
    if output_format == "jsonl" and existing:
        include_prompt = False

    new_content, count, truncated = read_files_as_text(
        files,
        output_format=output_format,
        include_prompt=include_prompt,
        inventory_text=inventory_text,
    )

    if count == 0:
        print("No decodable text files found", file=sys.stderr)
        if INVENTORY_TO_CLIPBOARD and inventory_text:
            inv_block = _inventory_comment_block(inventory_text, output_format=output_format)
            sep = "" if (not existing or existing.endswith("\n")) else "\n"
            pyperclip.copy(existing + sep + inv_block)
        return 1

    if not existing:
        final = new_content
    else:
        sep = "" if existing.endswith("\n") else "\n"
        final = existing + sep
        if output_format != "jsonl":
            final += "\n"
        final += new_content

    if len(final.encode("utf-8", errors="replace")) > MAX_TOTAL_BYTES:
        print("Append blocked: clipboard too large", file=sys.stderr)
        return 1

    pyperclip.copy(final)

    msg = f"Appended: {count} files"
    if truncated:
        msg += " (TRUNCATED)"
    print(msg, file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Clipboard copier (Windows-only).\n\n"
            "Commands (no flags):\n"
            "  r   replace clipboard (markdown)\n"
            "  a   append clipboard (markdown)\n"
            "  jr  replace clipboard (jsonl)\n"
            "  j   append clipboard (jsonl)\n\n"
            "Explorer-selection variants (suffix 'e'):\n"
            "  re  ae  jre  je\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("cmd", help="r|a|jr|j|re|ae|jre|je")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args()

    if args.cmd not in CMD_MAP:
        print(f"Invalid command: {args.cmd}", file=sys.stderr)
        return 1

    base_cmd, use_explorer = CMD_MAP[args.cmd]

    paths = []
    if use_explorer:
        sel = get_explorer_selected_paths()
        if not sel:
            print("No Explorer selection found.", file=sys.stderr)
            return 1
        paths.extend(sel)

    paths.extend(args.paths)

    if not paths:
        print("No input paths.", file=sys.stderr)
        return 1

    if base_cmd == "r":
        return replace_clipboard(paths, output_format="markdown")
    if base_cmd == "a":
        return append_clipboard(paths, output_format="markdown")
    if base_cmd == "jr":
        return replace_clipboard(paths, output_format="jsonl")
    if base_cmd == "j":
        return append_clipboard(paths, output_format="jsonl")

    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
