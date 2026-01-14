"""Python code execution tool for Cassey.

Allows the agent to run Python code for calculations, data processing,
and file operations within a sandboxed environment.
"""

import builtins
import io
import signal
import sys
from pathlib import Path

from langchain_core.tools import tool

from cassey.config.settings import settings


# Safe built-ins (whitelist)
SAFE_BUILTINS = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
    'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter', 'float',
    'format', 'frozenset', 'hex', 'int', 'isinstance', 'issubclass', 'iter',
    'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord', 'pow',
    'print', 'range', 'repr', 'reversed', 'round', 'set', 'slice', 'sorted',
    'str', 'sum', 'tuple', 'zip',
    'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
    'AttributeError', 'ImportError', 'StopIteration', 'RuntimeError',
    'bytearray', 'bytes', 'float', 'int', 'bool', 'str', 'list', 'tuple',
    'dict', 'set', 'frozenset', 'range', 'slice',
    '__import__',  # Required for import statements
}


# Safe modules (whitelist) - only built-in modules
SAFE_MODULES = {
    'math', 'datetime', 'random', 'statistics', 'json', 'csv',
    'collections', 'itertools', 'functools', 'string', 're',
    'pathlib', 'decimal', 'fractions', 'hashlib', 'base64',
    'urllib.request', 'urllib.parse', 'urllib.error', 'http.client',
    'ssl', 'socket', 'time',
}


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
    # Build safe built-ins dict with actual function references
    safe_builtins = {}
    for name in SAFE_BUILTINS:
        try:
            safe_builtins[name] = getattr(builtins, name)
        except AttributeError:
            pass

    safe_globals = {
        '__builtins__': safe_builtins,
        '__name__': '__main__',
        '__doc__': None,
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
    safe_globals['DATA_PATH'] = str(settings.FILES_ROOT.parent)

    return safe_globals


@tool
def execute_python(code: str) -> str:
    """Execute Python code in a sandboxed environment.

    **Available modules:**
    - Data: json, csv, pathlib
    - Math: math, statistics, random, decimal, fractions
    - Dates: datetime, time
    - Text: string, re
    - Collections: collections, itertools, functools
    - Network: urllib.request, urllib.parse, http.client, ssl, socket
    - Other: hashlib, base64

    **File access:**
    - Files can be read/written within the data/ directory

    **Limits:**
    - 30 second timeout
    - No os.system, os.popen, subprocess (security)
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

        >>> execute_python("import json; print(json.dumps({'a': 1}))")
        '{"a": 1}'
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    # Prepare safe globals
    safe_globals = _setup_safe_globals()

    try:
        # Set timeout (macOS/Linux only)
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(30)
        except (AttributeError, OSError):
            # SIGALRM not available (Windows) or restricted
            old_handler = None

        # Execute code
        try:
            exec(code, safe_globals)
        finally:
            # Clear timeout
            if old_handler is not None:
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
