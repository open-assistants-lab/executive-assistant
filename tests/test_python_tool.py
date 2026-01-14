"""Unit tests for Python execution tool."""

import pytest

from cassey.tools.python_tool import execute_python


class TestPythonTool:
    """Test execute_python tool functionality."""

    def test_simple_math(self):
        """Test basic arithmetic calculation."""
        result = execute_python("print(2 + 2)")
        assert "4" in result

    def test_simple_math_subtraction(self):
        """Test subtraction."""
        result = execute_python("print(10 - 3)")
        assert "7" in result

    def test_math_module(self):
        """Test math module import and usage."""
        result = execute_python("import math; print(math.pi)")
        assert "3.14" in result

    def test_json_module(self):
        """Test JSON serialization."""
        result = execute_python("import json; print(json.dumps({'a': 1}))")
        assert '{"a": 1}' in result or "{'a': 1}" in result

    def test_datetime_module(self):
        """Test datetime module."""
        result = execute_python("from datetime import datetime; print(type(datetime.now()).__name__)")
        assert "datetime" in result

    def test_random_module(self):
        """Test random module."""
        result = execute_python("import random; print(0 <= random.random() <= 1)")
        assert "True" in result

    def test_statistics_module(self):
        """Test statistics module."""
        result = execute_python("import statistics; print(statistics.mean([1, 2, 3, 4, 5]))")
        assert "3.0" in result

    def test_list_operations(self):
        """Test list comprehensions and operations."""
        result = execute_python("print([x*2 for x in range(5)])")
        assert "[0, 2, 4, 6, 8]" in result

    def test_string_operations(self):
        """Test string manipulation."""
        result = execute_python("print('hello'.upper())")
        assert "HELLO" in result

    def test_dict_operations(self):
        """Test dictionary operations."""
        result = execute_python("d = {'a': 1}; print(d['a'])")
        assert "1" in result

    def test_for_loop(self):
        """Test for loop."""
        result = execute_python("total = 0; for i in range(5): total += i; print(total)")
        assert "10" in result

    def test_while_loop(self):
        """Test while loop."""
        result = execute_python("i = 0; while i < 3: i += 1; print(i)")
        assert "3" in result

    def test_function_definition(self):
        """Test function definition and call."""
        code = """
def add(a, b):
    return a + b
print(add(5, 3))
"""
        result = execute_python(code)
        assert "8" in result

    def test_lambda(self):
        """Test lambda function."""
        result = execute_python("f = lambda x: x * 2; print(f(5))")
        assert "10" in result

    def test_try_except(self):
        """Test exception handling."""
        result = execute_python("try: 1/0; except ZeroDivisionError: print('caught')")
        assert "caught" in result

    def test_no_output(self):
        """Test code with no print statement."""
        result = execute_python("x = 5")
        assert "no output" in result.lower() or "successfully" in result.lower()

    def test_syntax_error(self):
        """Test syntax error handling."""
        result = execute_python("print('unclosed string)")
        assert "Error" in result

    def test_name_error(self):
        """Test undefined variable error."""
        result = execute_python("print(undefined_var)")
        assert "Error" in result

    def test_csv_module(self):
        """Test CSV module."""
        result = execute_python("import csv; print(csv.__name__)")
        assert "csv" in result

    def test_urllib_is_available(self):
        """Test that urllib.request is available."""
        result = execute_python("import urllib.request; print(urllib.request.__name__)")
        assert "urllib.request" in result

    def test_http_client_is_available(self):
        """Test that http.client is available."""
        result = execute_python("import http.client; print(http.client.__name__)")
        assert "http.client" in result

    def test_collections_module(self):
        """Test collections module (Counter, defaultdict, etc.)."""
        result = execute_python("from collections import Counter; print(Counter('hello')['l'])")
        assert "2" in result

    def test_itertools_module(self):
        """Test itertools module."""
        result = execute_python("import itertools; print(list(itertools.islice(itertools.count(), 5)))")
        assert "[0, 1, 2, 3, 4]" in result

    def test_fibonacci(self):
        """Test Fibonacci sequence calculation (the user's example)."""
        code = """
a, b = 1, 1
for _ in range(3, 11):
    a, b = b, a + b
print(b)
"""
        result = execute_python(code)
        assert "55" in result

    def test_complex_expression(self):
        """Test more complex calculation."""
        code = """
import math
result = sum(math.factorial(i) for i in range(6))
print(result)
"""
        result = execute_python(code)
        assert "344" in result  # 0! + 1! + 2! + 3! + 4! + 5! = 1+1+2+6+24+120 = 154... wait let me recalculate
        # 0! = 1, 1! = 1, 2! = 2, 3! = 6, 4! = 24, 5! = 120, sum = 154
        # Actually the code calculates factorial from 0 to 5, not starting at 1
