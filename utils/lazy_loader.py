#!/usr/bin/env python3
"""
Lazy Loading Utilities.

Defers expensive operations until actually needed.
"""

import logging
import threading
from functools import wraps
from typing import Any, Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class LazyValue(Generic[T]):
    """
    Lazy-loaded value that's computed on first access.

    Thread-safe lazy initialization.
    """

    def __init__(self, factory: Callable[[], T]):
        """
        Initialize lazy value.

        Args:
            factory: Function that creates the value
        """
        self._factory = factory
        self._value: Optional[T] = None
        self._initialized = False
        self._lock = threading.Lock()

    @property
    def value(self) -> T:
        """Get the value, computing it if necessary."""
        if not self._initialized:
            with self._lock:
                # Double-check after acquiring lock
                if not self._initialized:
                    self._value = self._factory()
                    self._initialized = True

        return self._value

    def is_initialized(self) -> bool:
        """Check if value has been computed."""
        return self._initialized

    def reset(self):
        """Reset lazy value to uninitialized state."""
        with self._lock:
            self._value = None
            self._initialized = False


class LazyProperty:
    """
    Descriptor for lazy-loaded properties.

    Usage:
        class MyClass:
            @LazyProperty
            def expensive_data(self):
                # This only runs once, on first access
                return load_expensive_data()
    """

    def __init__(self, func: Callable):
        self.func = func
        self.attr_name = f"_lazy_{func.__name__}"
        self.__doc__ = func.__doc__

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self

        # Check if already computed
        if not hasattr(obj, self.attr_name):
            # Compute and cache
            value = self.func(obj)
            setattr(obj, self.attr_name, value)

        return getattr(obj, self.attr_name)

    def __set__(self, obj, value):
        setattr(obj, self.attr_name, value)

    def __delete__(self, obj):
        if hasattr(obj, self.attr_name):
            delattr(obj, self.attr_name)


def lazy_import(module_name: str):
    """
    Lazy import decorator for modules.

    Defers module import until actually used.

    Usage:
        @lazy_import('expensive_module')
        def use_module(expensive_module):
            return expensive_module.do_something()
    """

    def decorator(func: Callable) -> Callable:
        _module = None
        _lock = threading.Lock()

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal _module

            if _module is None:
                with _lock:
                    if _module is None:
                        import importlib

                        _module = importlib.import_module(module_name)

            return func(_module, *args, **kwargs)

        return wrapper

    return decorator


class LazyDict(dict):
    """
    Dictionary with lazy value computation.

    Values are computed on first access using factory functions.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._factories: dict[str, Callable] = {}
        self._lock = threading.Lock()

    def set_lazy(self, key: str, factory: Callable[[], Any]):
        """Set a lazy value with factory function."""
        self._factories[key] = factory

    def __getitem__(self, key):
        # Check if it's a lazy value
        if key in self._factories and key not in self:
            with self._lock:
                # Double-check after lock
                if key not in self:
                    value = self._factories[key]()
                    super().__setitem__(key, value)

        return super().__getitem__(key)

    def get(self, key, default=None):
        """Get with lazy evaluation support."""
        try:
            return self[key]
        except KeyError:
            return default


# Convenience functions
def lazy_load(factory: Callable[[], T]) -> LazyValue[T]:
    """Create a lazy-loaded value."""
    return LazyValue(factory)
