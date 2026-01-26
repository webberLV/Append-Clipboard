#!/usr/bin/env python3
import os
import sys
import argparse
import pyperclip
from plyer import notification

# ---------------- Config ----------------
MAX_TOTAL_BYTES = 20 * 1024 * 1024   # 20 MB clipboard guard
MAX_FILE_BYTES  = 2 * 1024 * 1024    # 2 MB per-file guard

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
    ".log",
    ".tmp",
}

SKIP_FILENAMES = set()


def _is_minified_name(filename_lower: str) -> bool:
    return (
        filename_lower.endswith(".min.js")
        or filename_lower.endswith(".min.css")
        or filename_lower.endswith(".min.html")
    )


def should_skip_file(path: str) -> bool:
    filename = os.path.basename(path).lower()
    _, ext = os.path.splitext(filename)

    if filename in SKIP_FILENAMES:
        return True
    if ext in SKIP_EXTENSIONS:
        return True
    if _is_minified_name(filename):
        return True

    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return True
    except Exception:
        return True

    return False


def _looks_like_utf16_without_bom(b: bytes) -> str | None:
    if not b:
        return None

    nul_ratio = b.count(b"\x00") / len(b)
    if nul_ratio < 0.20:
        return None

    even = b[0::2]
    odd  = b[1::2]
    if not even or not odd:
        return None

    even_nul = even.count(b"\x00") / len(even)
    odd_nul  = odd.count(b"\x00") / len(odd)

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
        ".py": "python",
        ".bat": "batch",
        ".ps1": "powershell",
        ".reg": "registry",
        ".txt": "text",
        ".md": "markdown",
    }.get(ext, "text")


def get_file_priority(path: str):
    filename = os.path.basename(path).lower()

    priority_map = {
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


def get_all_files_in_folder(folder_path: str, explicitly_requested=False):
    """
    If explicitly_requested=True, ignore SKIP_DIRS and get everything inside.
    If False, respect SKIP_DIRS during recursive walk.
    """
    out = []
    try:
        for root, dirs, files in os.walk(folder_path):
            if not explicitly_requested:
                # Only filter subdirectories if this wasn't explicitly requested
                dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
            for f in files:
                p = os.path.join(root, f)
                if should_skip_file(p):
                    continue
                if is_probably_text(p):
                    out.append(p)
    except Exception as e:
        print(f"Error reading folder {folder_path}: {e}", file=sys.stderr)
    return out


def collect_files(paths):
    gathered = []
    for p in paths:
        if os.path.isfile(p):
            if not should_skip_file(p) and is_probably_text(p):
                gathered.append(p)
        elif os.path.isdir(p):
            # User explicitly passed this folder, so include everything inside
            gathered.extend(get_all_files_in_folder(p, explicitly_requested=True))
        else:
            print(f"Path not found: {p}", file=sys.stderr)

    gathered.sort(key=get_file_priority)

    seen = set()
    deduped = []
    for p in gathered:
        rp = os.path.normcase(os.path.abspath(p))
        if rp in seen:
            continue
        seen.add(rp)
        deduped.append(p)

    return deduped


def _looks_like_chrome_extension(file_paths, base_path=None) -> bool:
    for p in file_paths:
        name = os.path.basename(p).lower()
        if name == "manifest.json":
            return True
        if base_path:
            try:
                rel = os.path.relpath(p, base_path).replace("\\", "/").lower()
                if rel.endswith("/manifest.json"):
                    return True
            except Exception:
                pass
    return False


def generate_analysis_prompt(file_count, file_types, is_extension: bool):
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

    s += "---\n\n## Pasted Files (in review order)\n"
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


def read_files_as_text(file_paths, base_path=None):
    out = []
    file_types = {}
    total_bytes = 0
    count = 0
    truncated = False

    is_ext = _looks_like_chrome_extension(file_paths, base_path)

    for p in file_paths:
        try:
            raw = open(p, "rb").read()
        except Exception:
            continue

        text = _decode_bytes(raw)
        if text is None:
            continue

        disp = os.path.relpath(p, base_path) if base_path else p
        disp = disp.replace("\\", "/")

        ft = detect_file_type(p)
        file_types[ft] = file_types.get(ft, 0) + 1

        block = "\n".join([
            "=" * 80,
            f"FILE: {disp}",
            "=" * 80,
            text,
            "",
        ])

        bsz = len(block.encode("utf-8", errors="replace"))
        if total_bytes + bsz > MAX_TOTAL_BYTES:
            truncated = True
            break

        out.append(block)
        total_bytes += bsz
        count += 1

    prompt = generate_analysis_prompt(count, file_types, is_ext)
    return prompt + "\n".join(out), count, truncated


def show_notification(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="copy-clip",
            timeout=3,
        )
    except Exception:
        pass


def _determine_base_path(paths):
    if len(paths) == 1 and os.path.isdir(paths[0]):
        return paths[0]
    try:
        return os.path.commonpath(paths) if len(paths) > 1 else os.path.dirname(paths[0])
    except Exception:
        return None


def replace_clipboard(paths):
    files = collect_files(paths)
    if not files:
        show_notification("copy-clip", "No valid files found")
        return 1

    base = _determine_base_path(paths)
    content, count, truncated = read_files_as_text(files, base)
    if count == 0:
        show_notification("copy-clip", "No decodable text files found")
        return 1

    pyperclip.copy(content)
    note = f"Replaced clipboard: {count} files"
    if truncated:
        note += " (TRUNCATED)"
    show_notification("copy-clip", note)
    return 0


def append_clipboard(paths):
    files = collect_files(paths)
    if not files:
        show_notification("copy-clip", "No valid files found")
        return 1

    base = _determine_base_path(paths)
    new_content, count, truncated = read_files_as_text(files, base)
    if count == 0:
        show_notification("copy-clip", "No decodable text files found")
        return 1

    existing = pyperclip.paste()
    final = (existing + "\n\n" + new_content) if existing else new_content

    if len(final.encode("utf-8", errors="replace")) > MAX_TOTAL_BYTES:
        show_notification("copy-clip", "Append blocked: clipboard too large")
        return 1

    pyperclip.copy(final)
    note = f"Appended: {count} files"
    if truncated:
        note += " (TRUNCATED)"
    show_notification("copy-clip", note)
    return 0


def main():
    p = argparse.ArgumentParser(
        description="Copy project files to clipboard with an LLM review prompt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sp = p.add_subparsers(dest="cmd")

    r = sp.add_parser("r", help="Replace clipboard")
    r.add_argument("paths", nargs="+")

    a = sp.add_parser("a", help="Append clipboard")
    a.add_argument("paths", nargs="+")

    args = p.parse_args()
    if args.cmd == "r":
        return replace_clipboard(args.paths)
    if args.cmd == "a":
        return append_clipboard(args.paths)

    p.print_help()
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
