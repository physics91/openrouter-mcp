"""Handler registration helpers for the shared FastMCP instance."""

from importlib import import_module

_HANDLER_MODULES = (
    "chat",
    "collective_intelligence",
    "free_chat",
    "mcp_benchmark",
    "multimodal",
)
_handlers_registered = False


def register_handlers() -> None:
    """Import handler modules once so their MCP tools register explicitly."""
    global _handlers_registered

    if _handlers_registered:
        return

    for module_name in _HANDLER_MODULES:
        import_module(f"{__name__}.{module_name}")

    _handlers_registered = True


__all__ = ["register_handlers"]
