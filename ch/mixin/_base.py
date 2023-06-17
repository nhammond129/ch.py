"""Base mixin class with basic conflict detection"""
import inspect
from typing import Any


class Base():
    """Base mixin class to detect conflicting mixin"""
    def __new__(cls, *_arg: Any, **_kw: Any):
        overrides: dict[str, list[type]] = dict()
        for cla in cls.__mro__:
            if Base not in cla.__bases__:
                continue

            for name, _value in inspect.getmembers(cla):
                if name.startswith('__'):
                    # we do not check double underscore for conflict
                    continue

                if name in overrides:
                    print("[WARNING][mixin] potential conflicts:", name, *overrides[name], cla)
                else:
                    overrides.setdefault(name, []).append(cla)

        return super().__new__(cls)
