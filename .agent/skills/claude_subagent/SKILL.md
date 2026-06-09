---
name: using-local-utilities
description: Use when performing text processing, directory searches, file manipulation, or system status queries on this local host.
---

# Using Local Portable Utilities

## Overview
This local machine is equipped with a comprehensive suite of compiled native binaries (such as Rust-rewritten GNU coreutils and alternative search/multiplexing tools) available globally in the system environment PATH.

**Core Principle:** Always prefer executing these fast, compiled native utilities directly by name via shell commands instead of writing custom scratch Python scripts or installing external library dependencies.

## Comprehensive List of Available Tools (in PATH)

### 1. Advanced Alternatives
* **`fd`**: Super-fast directory search/walk. Use instead of nested Python walks or standard Windows `dir /s`.
* **`rip`**: Ergonomic and safe alternative to `rm`.
* **`pmux` / `psmux` / `tmux`**: Native terminal multiplexing on Windows PowerShell/Terminal.

### 2. File & Directory Management
* **`ls`**, **`dir`**, **`vdir`**: List directory contents.
* **`cp`**, **`mv`**, **`rm`**, **`ln`**, **`link`**, **`unlink`**: Copy, move, remove, and link files.
* **`mkdir`**, **`rmdir`**, **`mktemp`**: Create/delete directories and secure temp files.
* **`du`**, **`df`**: Disk space usage and filesystem checks.

### 3. Text Processing & Stream Filtering
* **`cat`**, **`head`**, **`tail`**, **`more`**: View or stream file contents.
* **`cut`**, **`paste`**, **`join`**: Extract or merge fields/columns from lines.
* **`tr`**, **`expand`**, **`unexpand`**: Translate, squeeze, or expand whitespace.
* **`sort`**, **`uniq`**, **`shuf`**: Sort, de-duplicate, or shuffle stream lines.
* **`wc`**: Fast line, word, and character counting (e.g. `wc -l filename`).
* **`fmt`**, **`fold`**, **`pr`**: Format and wrap text layouts.
* **`comm`**: Compare two sorted files line by line.

### 4. System Status & Environment
* **`env`**, **`printenv`**: List, view, or manipulate environment variables.
* **`whoami`**, **`hostname`**, **`tty`**: Identity and terminal properties.
* **`date`**, **`sleep`**: Time queries and execution delays.
* **`nproc`**: Retrieve number of available processing units.

### 5. Integrity & Security (Hashing)
* **`md5sum`**, **`sha256sum`**, **`sha512sum`**, **`sha1sum`**, **`sha224sum`**, **`sha384sum`**, **`b2sum`**: High-performance hash/checksum computation.

---

## ⚠️ Cross-Platform Guidelines

Because these utilities are native to the host environment, always adhere to the following rules regarding execution suffixes:

* **On Windows (PowerShell/cmd):** You can invoke utilities directly by name (e.g., `fd`, `wc`, `cat`). Appending `.exe` (e.g., `fd.exe`) is also acceptable but optional.
* **On Linux / macOS:** **NEVER append the `.exe` extension to any utility.** Running `.exe` files is prohibited on Unix-like operating systems. Always call them as standard Unix binaries (e.g., `fd`, `wc`, `cat`).

---

## Before/After Pattern

**❌ BAD (Slow, writes disk junk):**
```python
# Writing a scratch script just to count lines in a large text file
import sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    print(len(f.readlines()))
```

**✅ GOOD (Instant, native, cross-platform):**
```powershell
# On Windows
wc -l "large_file.txt"

# On Linux
wc -l "large_file.txt"
```

## Common Mistakes to Avoid
* **Suffixing `.exe` on Unix-like systems:** E.g., running `wc.exe` on Linux will result in a command-not-found or execution failure. Keep name references purely native.
* **Writing custom Python scripts** for text sorting, field cutting, or directory walking when `sort`, `cut`, or `fd` are already globally registered.
