from __future__ import annotations

from typing import Callable, Any


class Expression:
    def __init__(
        self,
        variables: list[str],
        label: str = "",
        function: Callable[..., Any] | None = None,
    ) -> None:
        self.variables = variables
        self.label = label
        self.function = (
            function
            if function is not None
            else (lambda *x: x[0] if len(x) == 1 else x)
        )

    def __repr__(self) -> str:
        return f"Expression({self.variables!r}, label={self.label!r})"
