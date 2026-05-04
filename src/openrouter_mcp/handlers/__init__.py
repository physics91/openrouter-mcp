"""Handler registration helpers for the shared FastMCP instance."""

_handlers_registered = False


def _load_handler_modules() -> tuple[object, ...]:
    from . import chat, collective_intelligence, free_chat, mcp_benchmark, multimodal

    return (chat, collective_intelligence, free_chat, mcp_benchmark, multimodal)


def register_handlers() -> None:
    """Import handler modules once so their MCP tools register explicitly."""
    global _handlers_registered

    if _handlers_registered:
        return

    _load_handler_modules()
    _handlers_registered = True


__all__ = ["register_handlers"]
