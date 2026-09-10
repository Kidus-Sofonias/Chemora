"""Performance benchmarking utilities for the chemistry engine."""

import functools
import time
from collections.abc import Callable
from typing import Any


class Timer:
    """Context manager for timing code blocks."""

    def __init__(self, name: str = ""):
        self.name = name
        self.elapsed = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed = time.perf_counter() - self.start

    def __repr__(self) -> str:
        return f"Timer({self.name}: {self.elapsed*1000:.2f}ms)"


def benchmark(func: Callable) -> Callable:
    """Decorator that logs execution time of a function."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[benchmark] {func.__name__}: {elapsed*1000:.2f}ms")
        return result
    return wrapper
