try:
    from importlib.metadata import version

    __version__ = version("django-markdown-middleware")
except Exception:
    __version__ = "HEAD"

from .middleware import MarkdownMiddleware, invalidate_cache  # noqa
