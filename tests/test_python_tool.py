"""Unit tests for Python execution tool."""

import pytest

from executive_assistant.tools.python_tool import execute_python
from executive_assistant.storage.file_sandbox import set_thread_id, clear_thread_id


class TestPythonTool:
    """Test execute_python tool functionality."""

    @pytest.fixture(autouse=True)
    def setup_thread_context(self):
        """Set up thread_id context for all tests to ensure files go to data/users/{thread_id}/files."""
        test_thread_id = "test:python_tool_thread"
        set_thread_id(test_thread_id)
        yield
        # Clean up
        clear_thread_id()

    def test_simple_math(self):
        """Test basic arithmetic calculation."""
        result = execute_python.invoke({"code": "print(2 + 2)"})
        assert "4" in result

    def test_simple_math_subtraction(self):
        """Test subtraction."""
        result = execute_python.invoke({"code": "print(10 - 3)"})
        assert "7" in result

    def test_math_module(self):
        """Test math module import and usage."""
        result = execute_python.invoke({"code": "import math; print(math.pi)"})
        assert "3.14" in result

    def test_json_module(self):
        """Test JSON serialization."""
        result = execute_python.invoke({"code": "import json; print(json.dumps({'a': 1}))"})
        assert '{"a": 1}' in result or "{'a': 1}" in result

    def test_datetime_module(self):
        """Test datetime module."""
        result = execute_python.invoke({"code": "import datetime; print(datetime.datetime.now().strftime('%Y-%m-%d'))"})
        assert "datetime" in result.lower() or "20" in result  # Year or datetime in output

    def test_random_module(self):
        """Test random module."""
        result = execute_python.invoke({"code": "import random; print(random.randint(1, 10) <= 10)"})
        assert "True" in result

    def test_statistics_module(self):
        """Test statistics module."""
        result = execute_python.invoke({"code": "import statistics; print(statistics.mean([1, 2, 3, 4, 5]))"})
        assert "3" in result  # Returns "3" not "3.0"

    def test_list_operations(self):
        """Test list comprehensions and operations."""
        result = execute_python.invoke({"code": "print([x * 2 for x in range(5)])"})
        assert "[0, 2, 4, 6, 8]" in result

    def test_string_operations(self):
        """Test string manipulation."""
        result = execute_python.invoke({"code": "print('hello'.upper())"})
        assert "HELLO" in result

    def test_dict_operations(self):
        """Test dictionary operations."""
        result = execute_python.invoke({"code": "d = {'a': 1}; print(d['a'])"})
        assert "1" in result

    def test_for_loop(self):
        """Test for loop."""
        code = """total = 0
for i in range(5):
    total += i
print(total)"""
        result = execute_python.invoke({"code": code})
        assert "10" in result

    def test_while_loop(self):
        """Test while loop."""
        code = """i = 0
while i < 3:
    i += 1
print(i)"""
        result = execute_python.invoke({"code": code})
        assert "3" in result

    def test_function_definition(self):
        """Test function definition and call."""
        code = """def add(a, b):
    return a + b
print(add(5, 3))"""
        result = execute_python.invoke({"code": code})
        assert "8" in result

    def test_lambda(self):
        """Test lambda function."""
        result = execute_python.invoke({"code": "f = lambda x: x * 2; print(f(5))"})
        assert "10" in result

    def test_try_except(self):
        """Test exception handling."""
        code = """try:
    1/0
except ZeroDivisionError:
    print('caught')"""
        result = execute_python.invoke({"code": code})
        assert "caught" in result

    def test_no_output(self):
        """Test code with no print statement."""
        result = execute_python.invoke({"code": "x = 5"})
        assert "no output" in result.lower() or "successfully" in result.lower()

    def test_syntax_error(self):
        """Test syntax error handling."""
        result = execute_python.invoke({"code": "if True"})
        assert "Error" in result

    def test_name_error(self):
        """Test undefined variable error."""
        result = execute_python.invoke({"code": "print(undefined_variable)"})
        assert "Error" in result

    def test_csv_module(self):
        """Test CSV module."""
        result = execute_python.invoke({"code": "import csv; print('csv module available')"})
        assert "csv" in result.lower()

    def test_urllib_is_available(self):
        """Test that urllib.request is available."""
        result = execute_python.invoke({"code": "import urllib.request; print('urllib.request available')"})
        assert "urllib.request" in result

    def test_http_client_is_available(self):
        """Test that http.client is available."""
        result = execute_python.invoke({"code": "import http.client; print('http.client available')"})
        assert "http.client" in result

    def test_collections_module(self):
        """Test collections module (Counter, defaultdict, etc.)."""
        result = execute_python.invoke({"code": "from collections import Counter; c = Counter('abca'); print(c['a'])"})
        assert "2" in result

    def test_itertools_module(self):
        """Test itertools module."""
        result = execute_python.invoke({"code": "import itertools; print(list(itertools.islice(itertools.count(), 5)))"})
        assert "[0, 1, 2, 3, 4]" in result

    def test_fibonacci(self):
        """Test Fibonacci sequence calculation (the user's example)."""
        code = """a, b = 1, 1
for _ in range(3, 11):
    a, b = b, a + b
print(b)"""
        result = execute_python.invoke({"code": code})
        assert "55" in result

    def test_complex_expression(self):
        """Test more complex calculation."""
        code = """import math
result = sum(math.factorial(i) for i in range(6))
print(result)"""
        result = execute_python.invoke({"code": code})
        # 0! + 1! + 2! + 3! + 4! + 5! = 1+1+2+6+24+120 = 154
        assert "154" in result

    # File I/O tests
    def test_file_write(self):
        """Test writing a file in the sandbox."""
        # Use a unique filename to avoid conflicts
        import time
        filename = f"test_write_{int(time.time())}.txt"
        code = f"""with open('{filename}', 'w') as f:
    f.write('Hello, sandbox!')
print('success')"""
        result = execute_python.invoke({"code": code})
        assert "success" in result

    def test_file_read(self):
        """Test reading a file in the sandbox."""
        import time
        filename = f"test_read_{int(time.time())}.txt"
        # First write a file
        write_code = f"""with open('{filename}', 'w') as f:
    f.write('Content to read')"""
        execute_python.invoke({"code": write_code})
        # Then read it
        read_code = f"""with open('{filename}', 'r') as f:
    content = f.read()
print(content)"""
        result = execute_python.invoke({"code": read_code})
        assert "Content to read" in result

    def test_file_write_and_read_json(self):
        """Test writing and reading JSON data."""
        import time
        filename = f"test_json_{int(time.time())}.json"
        code = f"""import json
data = {{'name': 'test', 'value': 123}}
with open('{filename}', 'w') as f:
    json.dump(data, f)

with open('{filename}', 'r') as f:
    loaded = json.load(f)
print(loaded['name'])"""
        result = execute_python.invoke({"code": code})
        assert "test" in result

    def test_csv_write(self):
        """Test writing CSV data."""
        import time
        filename = f"test_csv_{int(time.time())}.csv"
        code = f"""import csv
with open('{filename}', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['name', 'age'])
    writer.writerow(['Alice', 30])
    writer.writerow(['Bob', 25])
print('csv written')"""
        result = execute_python.invoke({"code": code})
        assert "csv written" in result

    def test_csv_read(self):
        """Test reading CSV data."""
        import time
        filename = f"test_csv_read_{int(time.time())}.csv"
        # First write CSV
        write_code = f"""import csv
with open('{filename}', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['name', 'age'])
    writer.writerow(['Alice', 30])"""
        execute_python.invoke({"code": write_code})
        # Then read it
        read_code = f"""import csv
with open('{filename}', 'r') as f:
    reader = csv.reader(f)
    rows = list(reader)
print(rows[1][0])"""
        result = execute_python.invoke({"code": read_code})
        assert "Alice" in result

    def test_path_traversal_blocked(self):
        """Test that path traversal attacks are blocked."""
        code = """with open('../../../etc/passwd', 'r') as f:
    print(f.read())"""
        result = execute_python.invoke({"code": code})
        assert "Security error" in result or "Path traversal blocked" in result or "Error" in result

    def test_disallowed_file_extension(self):
        """Test that files with disallowed extensions are blocked."""
        code = """with open('test.exe', 'w') as f:
    f.write('malicious')"""
        result = execute_python.invoke({"code": code})
        assert "Security error" in result or "not allowed" in result or "Error" in result


class TestPythonToolNoContext:
    """Test execute_python tool without thread context (should fail)."""

    def test_requires_thread_context(self):
        """Test that Python tool requires thread_id context."""
        from executive_assistant.storage.file_sandbox import clear_thread_id

        # Ensure no thread context is set
        clear_thread_id()

        # Should raise ValueError when trying to use file operations
        result = execute_python.invoke({"code": "with open('test.txt', 'w') as f: f.write('test')"})
        assert "thread_id context required" in result or "Error" in result
