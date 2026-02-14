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

import os
import sys
import argparse
import json
import pyperclip

import pythoncom  # pywin32
import win32com.client  # pywin32
import win32gui  # pywin32

if os.name != "nt":
    print("This script is Windows-only.", file=sys.stderr)
    sys.exit(1)

# ---------------- Config ----------------
MAX_TOTAL_BYTES = 20 * 1024 * 1024   # 20 MB clipboard guard
MAX_FILE_BYTES  = 2 * 1024 * 1024    # 2 MB per-file guard

INLINE_PATH_COMMENTS = True
USE_ABSOLUTE_PATHS = True

INVENTORY_TO_STDERR = True
INVENTORY_TO_CLIPBOARD = True

SKIP_DIRS = {
    "_locales", ".git", "node_modules", "dist", "build", "out",
    ".next", ".cache", "venv", ".venv", "__pycache__",
}

SKIP_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp4", ".avi", ".mov", ".wmv", ".mp3", ".wav",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".doc", ".docx",
    ".bak", ".map", ".log", ".tmp",
}

SKIP_FILENAMES = set()

ALLOW_FILENAMES = {
    "manifest.json",
    "package.json",
    "requirements.txt",
    "setup.py",
    "pyproject.toml",
    "CMakeLists.txt",
    "Makefile",
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

# ============================================================
# OPTION B: GLOBAL vs PLATFORM-SPECIFIC RULES
# ============================================================

# TRULY GLOBAL - applies to ALL codebases (platform-agnostic)
GLOBAL_REVIEW_REQUIREMENTS = [
    "CRITICAL BUGS FIRST - Highest-impact correctness bugs with exact FILE path + line numbers + quoted code snippets. No vague references.",
    "ROOT CAUSE ANALYSIS - Explain WHY it's broken, what the user experiences, and the underlying architectural flaw.",
    "PERFORMANCE ISSUES - Identify blocking operations, inefficient algorithms, unnecessary computation, resource exhaustion, memory leaks.",
    "COMPLETE FILE FIXES REQUIRED - Provide FULL file contents for every modification. No partial snippets. No 'update this section' - give the ENTIRE corrected file. If user intent is unclear or the requested approach is fundamentally flawed, STOP IMMEDIATELY and ask clarifying questions with 2-4 specific options.",
    "NO HALLUCINATED FILES - Only reference files that exist in the pasted codebase. Do not invent new files unless explicitly requested.",
    "SECURITY & ROBUSTNESS - Check for: input validation failures, exposed sensitive data, improper permission/access controls, race conditions, unhandled error cases.",
]

# CHROME EXTENSION ARCHITECTURAL RULES
EXTENSION_ARCHITECTURAL_RULES = [
    "ARCHITECTURAL VIOLATIONS - If code structure is fundamentally wrong, provide explicit remediation:",
    "  1) MISPLACED CODE: Background logic in popup.js, popup logic in service-worker.js, DOM access in background script, state tracking in popup instead of background",
    "  2) MISSING INFRASTRUCTURE: No chrome.runtime.onMessage handlers, missing message passing between contexts, no TabsInfo state tracking, scattered feature implementation",
    "  3) COMPONENT RESPONSIBILITIES:",
    "     - service-worker.js: Background tasks, alarms, persistent state, message routing, tab lifecycle management",
    "     - popup.js/popup.html: UI rendering only, request data via messages, no business logic, no state persistence",
    "     - content.js: DOM interaction only, forward events to background, no complex logic",
    "  4) REMEDIATION STEPS: Identify all misplaced code blocks ? Explain correct responsibilities ? Remove broken scaffolding ? Reimplement in proper location",
]

# PYTHON ARCHITECTURAL RULES
PYTHON_ARCHITECTURAL_RULES = [
    "ARCHITECTURAL VIOLATIONS - If code structure is fundamentally wrong, provide explicit remediation:",
    "  1) MISPLACED CODE: Business logic in UI code, database access in presentation layer, blocking I/O in async functions",
    "  2) MISSING INFRASTRUCTURE: No proper module separation, missing __init__.py files, circular imports, global mutable state",
    "  3) COMPONENT RESPONSIBILITIES:",
    "     - Core logic: Pure functions, business rules, domain models",
    "     - I/O layer: Database access, file operations, network calls (async)",
    "     - Presentation: CLI/GUI code, formatting, user interaction",
    "  4) REMEDIATION STEPS: Identify coupling violations ? Explain separation of concerns ? Refactor into proper layers",
]

# CPP ARCHITECTURAL RULES
CPP_ARCHITECTURAL_RULES = [
    "ARCHITECTURAL VIOLATIONS - If code structure is fundamentally wrong, provide explicit remediation:",
    "  1) MISPLACED CODE: Manual memory management where RAII should be used, raw pointers instead of smart pointers, resource cleanup in wrong scope",
    "  2) MISSING INFRASTRUCTURE: No RAII wrappers, missing move semantics, improper exception safety guarantees",
    "  3) COMPONENT RESPONSIBILITIES:",
    "     - Resource owners: Use RAII (unique_ptr, shared_ptr, containers), define rule-of-five if needed",
    "     - Value types: Proper copy/move semantics, const correctness",
    "     - Interfaces: Virtual destructors, pure virtual methods, proper inheritance hierarchies",
    "  4) REMEDIATION STEPS: Identify resource leaks ? Apply RAII patterns ? Implement proper ownership semantics",
]

# AUTOHOTKEY ARCHITECTURAL RULES
AUTOHOTKEY_ARCHITECTURAL_RULES = [
    "ARCHITECTURAL VIOLATIONS - If code structure is fundamentally wrong, provide explicit remediation:",
    "  1) MISPLACED CODE: Business logic in hotkey handlers, blocking operations without threads, COM cleanup in wrong scope",
    "  2) MISSING INFRASTRUCTURE: No error handlers for COM calls, missing window existence checks, no timeout handling",
    "  3) COMPONENT RESPONSIBILITIES:",
    "     - Hotkeys: Minimal logic, delegate to functions, use labels for complex operations",
    "     - Functions: Reusable logic, proper scope declarations (global/local), error handling with Try/Catch",
    "     - GUI: Event-driven handlers, proper cleanup with Gui Destroy, DPI-aware layouts",
    "  4) REMEDIATION STEPS: Identify scope violations ? Separate concerns ? Add proper error handling",
]

# JAVASCRIPT ARCHITECTURAL RULES
JAVASCRIPT_ARCHITECTURAL_RULES = [
    "ARCHITECTURAL VIOLATIONS - If code structure is fundamentally wrong, provide explicit remediation:",
    "  1) MISPLACED CODE: Business logic in UI components, data fetching in render functions, state management scattered across files",
    "  2) MISSING INFRASTRUCTURE: No proper state management, missing error boundaries, unhandled promise rejections",
    "  3) COMPONENT RESPONSIBILITIES:",
    "     - Components: Presentation logic only, props-based rendering, no direct API calls",
    "     - Services: API calls, data transformation, business logic",
    "     - State: Centralized store (Redux/Context), reducers for updates, selectors for derived data",
    "  4) REMEDIATION STEPS: Identify coupling ? Extract services ? Implement proper state flow",
]

# PLATFORM-SPECIFIC CHECKS
EXTENSION_CHECKS = [
    "Manifest.json - Verify MV3 compliance, correct permission scopes (activeTab vs tabs, host_permissions), service_worker declaration, content_scripts injection patterns, web_accessible_resources if needed",
    "Service Worker Lifecycle - Check: proper event registration (not inside async handlers), message listener setup timing, alarm/timer cleanup, storage initialization, self-termination handling, no reliance on global state persistence",
    "Message Passing Infrastructure - Verify: chrome.runtime.onMessage handlers in all contexts, proper sendMessage/sendResponse patterns, port-based connections for long-lived channels, error handling for disconnected contexts, no missing response acknowledgments",
    "Tabs API Misuse - Check: improper tab queries (missing windowId filters), stale tab references, missing tab removal listeners, executeScript timing issues, tab state assumptions without verification",
    "Event Listeners - Verify: proper cleanup on context invalidation, no duplicate registrations, removeListener calls in cleanup functions, alarm/timeout cleanup",
    "Storage & State - Check: chrome.storage.local consistency, race conditions on concurrent writes, missing error handlers, state synchronization between contexts, migration logic for schema changes",
    "Web Performance - Identify: unnecessary re-renders, blocking DOM operations, missing debouncing, redundant API calls, unhandled promise rejections",
    "Web Security - Check: XSS vulnerabilities, unsafe innerHTML usage, CSP violations, postMessage origin validation, missing error boundaries",
]

PYTHON_CHECKS = [
    "Type Safety - Check: missing type hints on public functions, inconsistent typing patterns, unhandled None returns, mutable default arguments, incorrect use of Any",
    "Error Handling - Verify: broad except clauses catching too much, missing context managers for resources (files, locks, connections), unhandled exceptions in async code, missing finally blocks for cleanup",
    "Performance Issues - Check: unnecessary list comprehensions with side effects, repeated expensive operations in loops, missing caching for pure functions, synchronous I/O in async contexts, inefficient string concatenation",
    "Memory Leaks - Verify: circular references, unclosed file handles, global state accumulation, dangling references in callbacks, missing __del__ or context manager cleanup",
    "Async/Await Patterns - Check: missing await keywords, blocking calls in async functions, improper use of asyncio.gather vs asyncio.wait, race conditions in concurrent tasks, missing timeout handling",
    "Module Structure - Verify: circular imports, missing __init__.py files, improper relative imports, global mutable state, missing if __name__ == '__main__' guards",
    "Security - Check: SQL injection vulnerabilities, unsafe eval/exec usage, hardcoded credentials, insecure random number generation, path traversal vulnerabilities, missing input sanitization",
]

AUTOHOTKEY_CHECKS = [
    "Hotkey Conflicts - Check: duplicate hotkey definitions, conflicting modifier combinations, missing tilde prefix for passthrough, improper use of $ prefix for hook hotkeys",
    "Variable Scope - Verify: missing global/local declarations, unintended variable shadowing, COM object cleanup, improper use of static variables",
    "Error Handling - Check: missing Try/Catch blocks around COM calls, unhandled window not found errors, missing timeout handling for WinWait, improper error propagation",
    "Performance - Verify: missing #NoEnv directive, excessive SetTimer frequency, blocking Sleep calls, redundant DetectHiddenWindows calls, missing A_TickCount optimization",
    "Window Management - Check: improper WinActivate timing, missing WinWaitActive verification, stale window handles, incorrect window title matching (exact vs contains vs regex)",
    "GUI Issues - Verify: missing Gui, Destroy on cleanup, memory leaks from unremoved controls, improper event handler registration, missing DPI awareness",
    "Compatibility - Check: v1 vs v2 syntax mixing, missing #Requires AutoHotkey directive, improper COM object release, missing 64-bit compatibility checks",
]

CPP_CHECKS = [
    "Memory Management - Check: missing delete/delete[] for new/new[], memory leaks in exception paths, double free vulnerabilities, use-after-free bugs, missing nullptr checks after allocation",
    "Resource Management - Verify: RAII pattern usage, missing destructor cleanup, resource leaks (file handles, mutexes, sockets), improper exception safety (basic, strong, nothrow guarantees)",
    "Undefined Behavior - Check: uninitialized variables, out-of-bounds array access, signed integer overflow, null pointer dereference, dangling pointers/references, violation of strict aliasing",
    "Concurrency Issues - Verify: data races (missing synchronization), deadlocks (lock ordering), improper mutex usage, missing memory barriers, thread-unsafe static initialization, race conditions in lazy initialization",
    "Modern C++ Violations - Check: raw pointers instead of smart pointers (unique_ptr, shared_ptr), manual memory management instead of RAII containers, C-style casts instead of static_cast/dynamic_cast, missing const correctness, lack of move semantics",
    "Performance Issues - Verify: unnecessary copies (missing std::move, pass-by-value for large objects), virtual function calls in tight loops, missing reserve() for vectors, inefficient string concatenation, cache-unfriendly data structures",
    "API Misuse - Check: buffer overflows in string operations (strcpy, sprintf), incorrect STL container usage, improper iterator invalidation handling, missing exception specifications, incorrect virtual destructor usage in inheritance hierarchies",
]

JAVASCRIPT_CHECKS = [
    "Async/Await Disasters - Missing await keywords, unhandled promise rejections, async function calls in sync contexts, Promise.all misuse, race conditions",
    "Resource Leaks - Unclosed connections, orphaned event listeners, DOM node references, interval/timeout cleanup, memory accumulation in long-lived contexts",
    "Error Handling - Try/catch coverage, error propagation, user-facing error messages, logging strategy, fallback behaviors",
    "Data Flow - State management patterns, data mutation tracking, prop drilling issues, unnecessary re-renders, stale closure references",
    "Type Safety - Missing null/undefined checks, inconsistent type coercion, missing input validation, improper use of any types in TypeScript",
    "Web Performance - Unnecessary re-renders, blocking DOM operations, missing debouncing/throttling, inefficient selectors, layout thrashing",
    "Web Security - XSS vulnerabilities, unsafe innerHTML/dangerouslySetInnerHTML, CSRF protection, secure cookie settings, postMessage origin validation",
]

GENERAL_CHECKS = [
    "Async/Await Disasters - Missing await keywords, unhandled promise rejections, async function calls in sync contexts, Promise.all misuse, race conditions",
    "Resource Leaks - Unclosed connections, orphaned event listeners, DOM node references, interval/timeout cleanup, memory accumulation in long-lived contexts",
    "Error Handling - Try/catch coverage, error propagation, user-facing error messages, logging strategy, fallback behaviors",
    "Data Flow - State management patterns, data mutation tracking, prop drilling issues, unnecessary re-renders, stale closure references",
]

# ============================================================
# NEW: Block system folders for Explorer-derived paths
# ============================================================

DENY_ROOTS = [
    os.environ.get("WINDIR", r"C:\Windows"),
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    os.environ.get("ProgramData", r"C:\ProgramData"),
]
DENY_DRIVE_ROOTS = True


def _norm_path(p: str) -> str:
    p = (p or "").strip().strip('"')
    p = os.path.normpath(p)
    p = os.path.abspath(p)
    return os.path.normcase(p)


def is_denied_explorer_path(p: str) -> bool:
    if not p:
        return True

    p = _norm_path(p)

    # Block non-filesystem shell namespaces / weird paths
    if not os.path.exists(p):
        return True

    if DENY_DRIVE_ROOTS:
        drive, tail = os.path.splitdrive(p)
        if drive and tail in (os.sep, ""):
            return True

    for root in DENY_ROOTS:
        if not root:
            continue
        r = _norm_path(root)
        if p == r or p.startswith(r + os.sep):
            return True

    return False


# ============================================================

def get_explorer_selected_paths():
    """
    Prefer ACTIVE (foreground) Explorer window.
    - If selection exists: return selected item paths (filtered against denied roots).
    - If no selection: return active folder path (filtered against denied roots).
    Returns [] if not Explorer foreground, or if path(s) are denied.
    """
    pythoncom.CoInitialize()
    try:
        fg_hwnd = win32gui.GetForegroundWindow()

        shell = win32com.client.Dispatch("Shell.Application")
        wins = shell.Windows()

        def _selected_items(doc):
            items = doc.SelectedItems()
            if items is None or items.Count <= 0:
                return []
            out = []
            for j in range(items.Count):
                it = items.Item(j)
                p = str(getattr(it, "Path", "")).strip()
                if p and not is_denied_explorer_path(p):
                    out.append(p)
            return out

        def _current_folder(doc):
            folder = getattr(doc, "Folder", None)
            if folder is None:
                return ""
            self_item = getattr(folder, "Self", None)
            if self_item is None:
                return ""
            p = str(getattr(self_item, "Path", "")).strip()
            if not p or is_denied_explorer_path(p):
                return ""
            return p

        # 1) Foreground Explorer only
        for i in range(wins.Count):
            w = wins.Item(i)
            try:
                full = str(getattr(w, "FullName", "")).lower()
                if not full.endswith("\\explorer.exe"):
                    continue

                hwnd = int(getattr(w, "HWND", 0))
                if hwnd != fg_hwnd:
                    continue

                doc = getattr(w, "Document", None)
                if doc is None:
                    return []

                sel = _selected_items(doc)
                if sel:
                    return sel

                folder_path = _current_folder(doc)
                if folder_path:
                    return [folder_path]

                return []
            except Exception:
                continue

        return []
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
        ".pyw": "python",
        ".ahk": "autohotkey",
        ".ahk2": "autohotkey",
        ".bat": "batch",
        ".ps1": "powershell",
        ".reg": "registry",
        ".txt": "text",
        ".md": "markdown",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "cpp_header",
        ".hpp": "cpp_header",
        ".hxx": "cpp_header",
    }.get(ext, "text")


def comment_prefix_for_type(ft: str) -> tuple[str, str] | None:
    if ft in ("javascript", "typescript", "batch", "powershell", "registry", "cpp", "c", "cpp_header"):
        return ("// ", "")
    if ft in ("python", "text", "markdown", "autohotkey"):
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
        "requirements.txt": 5,
        "setup.py": 6,
        "pyproject.toml": 7,
        "cmakelists.txt": 8,
        "makefile": 9,
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
        "main.py": 100,
        "__init__.py": 101,
        "__main__.py": 102,
        "main.cpp": 110,
        "main.c": 111,
        "main.ahk": 120,
        "readme.md": 800,
        "license": 810,
    }

    if filename in priority_map:
        return (priority_map[filename], path)

    ext = os.path.splitext(filename)[1].lower()
    return ({
        ".json": 200,
        ".py": 205,
        ".pyw": 205,
        ".js": 210,
        ".mjs": 210,
        ".cjs": 210,
        ".ts": 215,
        ".tsx": 215,
        ".cpp": 220,
        ".cc": 220,
        ".cxx": 220,
        ".c": 225,
        ".h": 230,
        ".hpp": 230,
        ".hxx": 230,
        ".ahk": 240,
        ".ahk2": 240,
        ".html": 300,
        ".css": 400,
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


def _detect_codebase_type(file_paths) -> str:
    """Detect what type of codebase this is based on file extensions."""
    extensions = {}
    for p in file_paths:
        ext = os.path.splitext(p)[1].lower()
        extensions[ext] = extensions.get(ext, 0) + 1

    # Check for Chrome extension
    if _looks_like_chrome_extension(file_paths):
        return "chrome_extension"

    # Count file types
    py_count = extensions.get(".py", 0) + extensions.get(".pyw", 0)
    cpp_count = extensions.get(".cpp", 0) + extensions.get(".cc", 0) + extensions.get(".cxx", 0) + extensions.get(".c", 0) + extensions.get(".h", 0) + extensions.get(".hpp", 0)
    ahk_count = extensions.get(".ahk", 0) + extensions.get(".ahk2", 0)
    js_count = extensions.get(".js", 0) + extensions.get(".ts", 0) + extensions.get(".jsx", 0) + extensions.get(".tsx", 0)

    # Determine primary type (threshold: >30% of files)
    total = sum(extensions.values())
    if total == 0:
        return "general"

    if py_count / total > 0.3:
        return "python"
    if cpp_count / total > 0.3:
        return "cpp"
    if ahk_count / total > 0.3:
        return "autohotkey"
    if js_count / total > 0.3:
        return "javascript"

    return "general"


def generate_analysis_prompt(file_count, file_types, codebase_type: str, output_format: str):
    """
    Markdown mode prompt (commands: r, a)
    Option B: Global requirements + platform-specific architecture + platform-specific checks
    """
    type_headers = {
        "chrome_extension": "# Chrome Extension Code Review\n",
        "python": "# Python Code Review\n",
        "cpp": "# C++ Code Review\n",
        "autohotkey": "# AutoHotkey Script Review\n",
        "javascript": "# JavaScript/TypeScript Code Review\n",
        "general": "# Codebase Review\n",
    }

    header = type_headers.get(codebase_type, "# Codebase Review\n")

    s = header + "\n"
    s += "## Input Summary\n"
    s += f"- Total files pasted: {file_count}\n"
    s += "- File type counts: " + ", ".join(f"{k}({v})" for k, v in file_types.items()) + "\n\n"

    # GLOBAL requirements (apply to all codebases)
    s += "## Global Requirements\n"
    for i, req in enumerate(GLOBAL_REVIEW_REQUIREMENTS, 1):
        s += f"{i}) {req}\n"
    s += "\n"

    # PLATFORM-SPECIFIC architectural rules
    architectural_rules = {
        "chrome_extension": EXTENSION_ARCHITECTURAL_RULES,
        "python": PYTHON_ARCHITECTURAL_RULES,
        "cpp": CPP_ARCHITECTURAL_RULES,
        "autohotkey": AUTOHOTKEY_ARCHITECTURAL_RULES,
        "javascript": JAVASCRIPT_ARCHITECTURAL_RULES,
    }

    if codebase_type in architectural_rules:
        s += "## Architectural Rules\n"
        for rule in architectural_rules[codebase_type]:
            s += f"{rule}\n"
        s += "\n"

    # PLATFORM-SPECIFIC checks
    platform_checks = {
        "chrome_extension": ("Chrome Extension Specific Checks", EXTENSION_CHECKS),
        "python": ("Python Specific Checks", PYTHON_CHECKS),
        "cpp": ("C++ Specific Checks", CPP_CHECKS),
        "autohotkey": ("AutoHotkey Specific Checks", AUTOHOTKEY_CHECKS),
        "javascript": ("JavaScript/TypeScript Specific Checks", JAVASCRIPT_CHECKS),
        "general": ("General Codebase Checks", GENERAL_CHECKS),
    }

    check_title, checks = platform_checks.get(codebase_type, ("General Checks", GENERAL_CHECKS))
    s += f"## {check_title}\n"
    for check in checks:
        s += f"- {check}\n"
    s += "\n"

    if output_format == "jsonl":
        s += "## Format\n"
        s += "Each subsequent line is a JSON object with fields: path, type, content.\n"
        s += "Use content as the exact file text (newlines preserved via JSON escapes).\n\n"

    s += "---\n\n## Pasted Files\n"
    s += "(Each file begins with a FILE: path comment.)\n\n"
    return s


def generate_jsonl_controller(codebase_type: str):
    """
    JSONL mode controller (commands: jr, j) when agents.md is not present.
    Option B: Global requirements + platform-specific architecture + platform-specific checks
    """
    lines = []
    lines.append("# Controller")
    lines.append("# If AGENTS.MD is present, it is authoritative and overrides this fallback.")
    lines.append("#")
    lines.append("# Global requirements:")

    for i, req in enumerate(GLOBAL_REVIEW_REQUIREMENTS, 1):
        lines.append(f"# {i}) {req}")

    lines.append("#")

    # PLATFORM-SPECIFIC architectural rules
    architectural_rules = {
        "chrome_extension": ("Chrome Extension architectural rules:", EXTENSION_ARCHITECTURAL_RULES),
        "python": ("Python architectural rules:", PYTHON_ARCHITECTURAL_RULES),
        "cpp": ("C++ architectural rules:", CPP_ARCHITECTURAL_RULES),
        "autohotkey": ("AutoHotkey architectural rules:", AUTOHOTKEY_ARCHITECTURAL_RULES),
        "javascript": ("JavaScript/TypeScript architectural rules:", JAVASCRIPT_ARCHITECTURAL_RULES),
    }

    if codebase_type in architectural_rules:
        arch_title, arch_rules = architectural_rules[codebase_type]
        lines.append(f"# {arch_title}")
        for rule in arch_rules:
            lines.append(f"# {rule}")
        lines.append("#")

    # PLATFORM-SPECIFIC checks
    platform_checks = {
        "chrome_extension": ("Chrome Extension checks (MV3):", EXTENSION_CHECKS),
        "python": ("Python specific checks:", PYTHON_CHECKS),
        "cpp": ("C++ specific checks:", CPP_CHECKS),
        "autohotkey": ("AutoHotkey specific checks:", AUTOHOTKEY_CHECKS),
        "javascript": ("JavaScript/TypeScript specific checks:", JAVASCRIPT_CHECKS),
        "general": ("General checks:", GENERAL_CHECKS),
    }

    check_title, checks = platform_checks.get(codebase_type, ("General checks:", GENERAL_CHECKS))
    lines.append(f"# {check_title}")
    for check in checks:
        lines.append(f"# - {check}")

    lines.append("#")
    lines.append("# Format:")
    lines.append("# JSONL records follow with fields: {path, type, content}.")
    lines.append("# Do not treat this controller as a file; JSONL records start below.")

    return "\n".join(lines).rstrip() + "\n\n"


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
    - jsonl: comment lines starting with "# "
    """
    if not inventory_text:
        return ""

    if output_format == "jsonl":
        lines = inventory_text.splitlines()
        return "".join("# " + line + "\n" for line in lines) + "\n"

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

    codebase_type = _detect_codebase_type(file_paths)

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
            controller_text = generate_jsonl_controller(codebase_type)

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

    prompt = generate_analysis_prompt(count, file_types, codebase_type, output_format) if include_prompt else ""
    return inv_block + prompt + "".join(out), count, truncated


def replace_clipboard(paths, output_format="markdown"):
    files, inventory_text = collect_files_and_inventory(paths)
    if not files:
        print("No valid files found", file=sys.stderr)
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
            print("No Explorer selection/folder found (or blocked system folder).", file=sys.stderr)
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
