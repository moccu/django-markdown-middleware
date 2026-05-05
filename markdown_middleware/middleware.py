import hashlib
import uuid

from django.conf import settings
from django.core.cache import cache
from html_to_markdown import convert

CACHE_KEY_PREFIX = "markdown_middleware"


def invalidate_cache(path):
    """Delete all cached markdown responses for the given path, across all query strings."""
    digest = hashlib.sha256(path.encode()).hexdigest()
    cache.delete(f"{CACHE_KEY_PREFIX}:path:{digest}")


class MarkdownMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def get_path_cache_key(self, request):
        """Return the cache key under which this path's token is stored."""
        digest = hashlib.sha256(request.path.encode()).hexdigest()
        return f"{CACHE_KEY_PREFIX}:path:{digest}"

    def get_full_cache_key(self, request):
        """
        Return the response cache key for this request.

        Ensures a path token exists, creating one if necessary. The key combines
        a per-path token with a hash of the query string, so that invalidating
        the path token makes all query string variants unreachable.
        """
        path_key = self.get_path_cache_key(request)
        path_token = cache.get(path_key)
        if path_token is None:
            cache_timeout = getattr(settings, "MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT", None)
            path_token = uuid.uuid4().hex
            cache.set(path_key, path_token, cache_timeout)

        qs_digest = hashlib.sha256(request.META.get("QUERY_STRING", "").encode()).hexdigest()

        return f"{CACHE_KEY_PREFIX}:{path_token}:{qs_digest}"

    def __call__(self, request):
        """
        Process the request and convert HTML responses to Markdown when appropriate.

        Passes the request through unchanged unless all of the following are true:
        - The request method is GET.
        - The request carries an ``Accept: text/markdown`` header.
        - ``MARKDOWN_MIDDLEWARE_ANONYMOUS_ONLY`` is False, or the user is not authenticated.
        - The response has HTTP status 200 and a ``text/html`` content type.

        When conversion takes place the response body is replaced with the Markdown
        equivalent, ``Content-Type`` is set to ``text/markdown``, and an
        ``X-Markdown-Tokens`` header with an estimated token count is added.

        If ``MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT`` is set the converted response is
        cached and served from cache on subsequent matching requests. The cache key
        is computed once and reused for both the cache read and write.
        """
        if request.method != "GET":
            return self.get_response(request)

        accept = request.META.get("HTTP_ACCEPT", "")
        if "text/markdown" not in accept:
            return self.get_response(request)

        anonymous_only = getattr(settings, "MARKDOWN_MIDDLEWARE_ANONYMOUS_ONLY", True)
        if anonymous_only and getattr(
            getattr(request, "user", None), "is_authenticated", False
        ):
            return self.get_response(request)

        cache_timeout = getattr(settings, "MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT", None)
        cache_key = self.get_full_cache_key(request) if cache_timeout is not None else None

        if cache_key is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        response = self.get_response(request)

        if response.status_code != 200:
            return response

        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        html = response.content.decode(response.charset or "utf-8")
        result = convert(html)
        markdown = result.content

        # To calculate the number of tokens needed for Markdown,
        # you can estimate that one token generally corresponds to
        # about 4 characters of text.
        token_count = len(markdown) // 4

        response.content = markdown.encode("utf-8")
        response["Content-Type"] = "text/markdown; charset=utf-8"
        response["Content-Length"] = len(response.content)
        response["X-Markdown-Tokens"] = str(token_count)

        if cache_key is not None:
            cache.set(cache_key, response, cache_timeout)

        return response
