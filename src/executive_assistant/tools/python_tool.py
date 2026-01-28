"""Python code execution tool for Executive Assistant.

Allows the agent to run Python code for calculations, data processing,
and file operations within a sandboxed environment.
"""

import builtins
import io
import os
import signal
import sys
from pathlib import Path

from langchain_core.tools import tool

from executive_assistant.config.settings import settings


# Allowed file extensions for Python sandbox file I/O
ALLOWED_FILE_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml',
    '.csv', '.xml', '.html', '.css', '.sh', '.bash', '.log', '.pdf',
    '.docx', '.pptx', '.xlsx',
}

# Maximum file size for Python sandbox (10MB default)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


# Safe built-ins (whitelist)
# SECURITY: __import__ is NOT included - we provide a custom wrapper that enforces SAFE_MODULES
SAFE_BUILTINS = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
    'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter', 'float',
    'format', 'frozenset', 'hex', 'int', 'isinstance', 'issubclass', 'iter',
    'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord', 'pow',
    'print', 'range', 'repr', 'reversed', 'round', 'set', 'slice', 'sorted',
    'str', 'sum', 'tuple', 'zip',
    'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
    'AttributeError', 'ImportError', 'StopIteration', 'RuntimeError',
    'ZeroDivisionError', 'FileNotFoundError', 'IOError', 'OSError',
    'bytearray', 'bytes', 'float', 'int', 'bool', 'str', 'list', 'tuple',
    'dict', 'set', 'frozenset', 'range', 'slice',
    'type',  # For type checking
    'Path',  # For path operations
}


# Safe modules (whitelist) - only built-in modules
# SECURITY: 'os' and 'socket' are excluded to prevent command execution and network attacks
SAFE_MODULES = {
    'math', 'datetime', 'random', 'statistics', 'json', 'csv',
    'collections', 'itertools', 'functools', 'string', 're',
    'pathlib', 'decimal', 'fractions', 'hashlib', 'base64',
    'urllib.request', 'urllib.parse', 'urllib.error', 'http.client',
    'ssl', 'time', 'pypdf',  # os and socket removed for security
    'fitz', 'docx', 'pptx', 'openpyxl',
    'markdown_it', 'bs4', 'lxml', 'html5lib', 'PIL', 'reportlab',
    'dateparser', 'dateutil',
}


def _get_thread_root() -> Path:
    """Get the context-specific root directory for file operations.

    Priority:
    1. thread_id context -> data/users/{thread_id}/files/
    """
    from executive_assistant.storage.thread_storage import get_thread_id

    thread_id = get_thread_id()
    if thread_id:
        thread_root = settings.get_thread_files_path(thread_id)
        thread_root.mkdir(parents=True, exist_ok=True)
        return thread_root

    raise ValueError("No thread_id context available for Python tool file access")


def _validate_path(path: str | Path) -> Path:
    """Validate that a path is within the allowed thread-specific directory.

    Args:
        path: Path to validate (can be absolute or relative)

    Returns:
        Resolved absolute path within the thread's data directory

    Raises:
        SecurityError: If path traversal attempt detected or outside allowed directory
    """
    thread_root = _get_thread_root().resolve()

    if isinstance(path, str):
        path = Path(path)

    # If path is absolute, check it directly
    # If relative, resolve against thread root
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (thread_root / path).resolve()

    # Check for path traversal - ensure resolved path is within thread_root
    try:
        resolved.relative_to(thread_root)
    except ValueError:
        raise SecurityError(
            f"Path traversal blocked: {resolved} is outside thread directory {thread_root}"
        )

    # Check file extension
    if resolved.is_file() or not resolved.exists():
        # Check extension for new files or existing files
        if resolved.suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
            raise SecurityError(
                f"File type '{resolved.suffix}' not allowed. Allowed types: {allowed}"
            )

    return resolved


class SecurityError(Exception):
    """Raised when a security constraint is violated."""
    pass


class SandboxedFile:
    """Sandboxed file object that enforces security constraints."""

    def __init__(self, path: str | Path, mode: str = 'r', encoding: str = 'utf-8', newline: str | None = None):
        self.path = _validate_path(path)
        self.mode = mode
        self.encoding = encoding
        self.newline = newline
        self._file = None
        self._content_to_write = []

    def __enter__(self):
        # Create parent directory if needed (for write modes)
        if any(c in self.mode for c in 'wxa'):
            self.path.parent.mkdir(parents=True, exist_ok=True)

        # Open file with appropriate parameters
        if self.newline is not None:
            self._file = open(self.path, self.mode, encoding=self.encoding, newline=self.newline)
        elif 'b' in self.mode:
            self._file = open(self.path, self.mode)
        else:
            self._file = open(self.path, self.mode, encoding=self.encoding)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def read(self, size: int = -1) -> str:
        """Read from file."""
        if not self._file:
            raise ValueError("File not open. Use 'with open()' statement.")
        return self._file.read(size)

    def write(self, content: str) -> int:
        """Write to file with size validation."""
        if not self._file:
            raise ValueError("File not open. Use 'with open()' statement.")

        # Track content for final size check
        self._content_to_write.append(content)

        # Check total size
        total_size = sum(len(c.encode()) for c in self._content_to_write)
        if total_size > MAX_FILE_SIZE_BYTES:
            raise SecurityError(
                f"File size {total_size} bytes exceeds limit {MAX_FILE_SIZE_BYTES} bytes"
            )

        return self._file.write(content)

    def readline(self, size: int = -1) -> str:
        """Read a line from file."""
        if not self._file:
            raise ValueError("File not open. Use 'with open()' statement.")
        return self._file.readline(size)

    def readlines(self, hint: int = -1) -> list[str]:
        """Read all lines from file."""
        if not self._file:
            raise ValueError("File not open. Use 'with open()' statement.")
        return self._file.readlines(hint)

    def __iter__(self):
        """Iterate over lines."""
        if not self._file:
            raise ValueError("File not open. Use 'with open()' statement.")
        return self._file

    def __next__(self):
        return next(self._file)


def sandboxed_open(path: str | Path, mode: str = 'r', encoding: str = 'utf-8', **kwargs) -> SandboxedFile:
    """Open a file within the thread-scoped sandbox directory.

    This is a security-wrapped version of open() that:
    - Scopes files to the current conversation/thread (isolation between users)
    - Only allows access within the thread's data directory
    - Prevents path traversal attacks (e.g., ../../../etc/passwd)
    - Restricts file extensions to safe types
    - Enforces maximum file size limits

    Args:
        path: File path (relative to thread's directory)
        mode: File open mode ('r', 'w', 'a', 'x', etc.)
        encoding: Text encoding (default: utf-8)
        **kwargs: Additional arguments (e.g., newline='') passed to open()

    Returns:
        A SandboxedFile object for use with 'with' statement

    Examples:
        >>> with open('output.txt', 'w') as f:
        ...     f.write('Hello, world!')
        >>> with open('output.txt', 'r') as f:
        ...     content = f.read()

    Raises:
        SecurityError: If path is outside thread directory or extension not allowed
    """
    # Extract newline parameter if provided
    newline = kwargs.get('newline')
    return SandboxedFile(path, mode, encoding, newline)


class _TimeoutError(Exception):
    """Timeout exception for code execution."""
    pass


def _timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise _TimeoutError("Code execution exceeded 30 second timeout")


def _import_safe_module(name: str):
    """Import a module if it's in the whitelist."""
    # Handle dotted modules like urllib.request
    parts = name.split('.')
    for i in range(len(parts), 0, -1):
        prefix = '.'.join(parts[:i])
        if prefix in SAFE_MODULES:
            try:
                return __import__(name, fromlist=['*'])
            except ImportError:
                continue
    raise ImportError(f"Module '{name}' is not allowed")


def _setup_safe_globals():
    """Create a safe globals dictionary for code execution."""
    # Add custom __import__ that enforces SAFE_MODULES whitelist
    # This prevents bypassing the module restrictions
    def _safe_import(name, *args, **kwargs):
        """Custom __import__ that only allows whitelisted modules."""
        # Handle dotted modules like urllib.request
        parts = name.split('.')
        for i in range(len(parts), 0, -1):
            prefix = '.'.join(parts[:i])
            if prefix in SAFE_MODULES:
                # Use the real __import__ for whitelisted modules
                return builtins.__import__(name, *args, **kwargs)
        raise ImportError(
            f"Module '{name}' is not allowed in sandbox. "
            f"Allowed modules: {', '.join(sorted(SAFE_MODULES))}"
        )

    # Build safe built-ins dict with actual function references
    safe_builtins = {}
    for name in SAFE_BUILTINS:
        try:
            safe_builtins[name] = getattr(builtins, name)
        except AttributeError:
            pass

    # Add custom __import__ to safe_builtins so Python's import statement works
    safe_builtins['__import__'] = _safe_import

    safe_globals = {
        '__builtins__': safe_builtins,
        '__name__': '__main__',
        '__doc__': None,
        '__import__': _safe_import,  # Also add at top level for direct access
    }

    # Import safe modules
    for mod_name in SAFE_MODULES:
        try:
            safe_globals[mod_name] = __import__(mod_name)
        except ImportError:
            pass

    # Add convenience aliases for urllib
    try:
        import urllib.request
        import urllib.parse
        import urllib.error
        safe_globals['urllib'] = urllib  # top-level module
        safe_globals['urllib_request'] = urllib.request
        safe_globals['urllib_parse'] = urllib.parse
        safe_globals['urllib_error'] = urllib.error
        safe_globals['urlopen'] = urllib.request.urlopen
        safe_globals['Request'] = urllib.request.Request
        safe_globals['URLError'] = urllib.error.URLError
    except ImportError:
        pass

    # Add data directory path
    safe_globals['DATA_PATH'] = str(settings.USERS_ROOT.parent)

    # Add sandboxed file operations
    safe_globals['open'] = sandboxed_open
    safe_globals['SecurityError'] = SecurityError
    return safe_globals


@tool
def execute_python(code: str) -> str:
    """Execute Python code in a sandboxed environment.

    **Available modules:**
    - Data: json, csv, pathlib, pypdf, docx, pptx, openpyxl, fitz, markdown_it, bs4, lxml, html5lib, PIL, reportlab, dateparser, dateutil
    - Math: math, statistics, random, decimal, fractions
    - Dates: datetime, time
    - Text: string, re
    - Collections: collections, itertools, functools
    - Network: urllib.request, urllib.parse, http.client, ssl
    - Other: hashlib, base64

    **File access with open():**
    - Files are scoped to the current conversation/thread (isolation between users)
    - Allowed extensions: .txt, .md, .py, .js, .ts, .json, .yaml, .yml, .csv, .xml, .html, .css, .sh, .bash, .log, .pdf, .docx, .pptx, .xlsx
    - Path traversal is blocked (e.g., ../../../etc/passwd)
    - Max file size: 10MB

    **PDF processing:**
    - Use `pypdf` to read PDF files downloaded via urllib.request
    - Example: Download from URL and extract text

    **Limits:**
    - 30 second timeout
    - No os, socket, subprocess, or system commands (security)
    - No eval, exec (code injection prevention)

    Args:
        code: Python code to execute

    Returns:
        Output from print() statements or success/error message

    Examples:
        >>> execute_python("print(2 + 2)")
        "4"

        >>> execute_python("import math; print(math.pi)")
        "3.14159..."

        >>> execute_python("with open('test.txt', 'w') as f: f.write('Hello')")
        "File written: test.txt"

        >>> execute_python("import urllib.request; f = urllib.request.urlopen('https://example.com'); print(f.read(100)[:50])")
        "<!doctype html>..."

        >>> execute_python("import pypdf; from pypdf import PdfReader; print('PDF module loaded')")
        "PDF module loaded"
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    # Prepare safe globals
    safe_globals = _setup_safe_globals()

    try:
        # Set timeout using multiprocessing or threading (signals don't work in threads)
        # For threaded environments, skip signal-based timeout
        timeout_enabled = False
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(30)
            timeout_enabled = True
        except (AttributeError, OSError, ValueError):
            # SIGALRM not available: Windows, threads, or restricted environments
            pass

        # Execute code
        cwd = None
        try:
            try:
                from executive_assistant.storage.file_sandbox import get_sandbox
                sandbox = get_sandbox()
                cwd = Path.cwd()
                os.chdir(sandbox.root)
            except Exception:
                cwd = None
            exec(code, safe_globals)
        finally:
            if cwd is not None:
                os.chdir(cwd)
            # Clear timeout
            if timeout_enabled:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        # Get output
        output = sys.stdout.getvalue()
        return output if output else "Code executed successfully (no output)"

    except _TimeoutError as e:
        return f"Timeout: {e}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
    finally:
        sys.stdout = old_stdout


def get_python_tools() -> list:
    """Get Python execution tools."""
    return [execute_python]
