import pytest
from django.core.cache import cache
from django.http import HttpResponse

from markdown_middleware.middleware import MarkdownMiddleware, invalidate_cache

HTML_RESPONSE = "<html><head></head><body><h1>Hello</h1><p>World</p></body></html>"


def make_html_response(content=HTML_RESPONSE, status=200):
    return HttpResponse(content, content_type="text/html; charset=utf-8", status=status)


def make_middleware(response_factory=None):
    if response_factory is None:

        def response_factory(response):
            return make_html_response()

    return MarkdownMiddleware(response_factory)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class TestMarkdownMiddleware:
    def test_non_get_request_passes_through(self, rf):
        middleware = make_middleware()
        response = middleware(rf.post("/", HTTP_ACCEPT="text/markdown"))
        assert response["Content-Type"] == "text/html; charset=utf-8"

    def test_no_accept_header_passes_through(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/"))
        assert response["Content-Type"] == "text/html; charset=utf-8"
        assert response.content == HTML_RESPONSE.encode()

    def test_unrelated_accept_header_passes_through(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/", HTTP_ACCEPT="application/json"))
        assert response["Content-Type"] == "text/html; charset=utf-8"

    def test_non_200_response_passes_through(self, rf):
        middleware = MarkdownMiddleware(lambda r: HttpResponse("Not Found", status=404))
        response = middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        assert response.status_code == 404
        assert "X-Markdown-Tokens" not in response

    def test_non_html_content_type_passes_through(self, rf):
        middleware = MarkdownMiddleware(
            lambda r: HttpResponse('{"key": "value"}', content_type="application/json")
        )
        response = middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        assert response["Content-Type"] == "application/json"
        assert "X-Markdown-Tokens" not in response

    def test_html_converted_to_markdown(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        assert response.status_code == 200
        assert "text/markdown" in response["Content-Type"]
        content = response.content.decode("utf-8")
        assert "Hello" in content
        assert "World" in content

    def test_content_type_set_to_markdown(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        assert response["Content-Type"] == "text/markdown; charset=utf-8"

    def test_x_markdown_tokens_header_present(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        assert "X-Markdown-Tokens" in response
        assert int(response["X-Markdown-Tokens"]) >= 0

    def test_x_markdown_tokens_value_matches_content(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        markdown = response.content.decode("utf-8")
        expected = len(markdown) // 4
        assert int(response["X-Markdown-Tokens"]) == expected

    def test_content_length_updated(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        assert int(response["Content-Length"]) == len(response.content)

    def test_accept_header_with_multiple_types(self, rf):
        middleware = make_middleware()
        response = middleware(rf.get("/", HTTP_ACCEPT="text/html, text/markdown, */*"))
        assert "text/markdown" in response["Content-Type"]

    def test_response_is_cached(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT = 60
        call_count = 0

        def get_response(request):
            nonlocal call_count
            call_count += 1
            return make_html_response()

        middleware = MarkdownMiddleware(get_response)
        middleware(rf.get("/cached/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/cached/", HTTP_ACCEPT="text/markdown"))
        assert call_count == 1

    def test_cached_response_returned(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT = 60
        middleware = make_middleware()
        first = middleware(rf.get("/cached/", HTTP_ACCEPT="text/markdown"))
        second = middleware(rf.get("/cached/", HTTP_ACCEPT="text/markdown"))
        assert first.content == second.content
        assert second["X-Markdown-Tokens"] == first["X-Markdown-Tokens"]

    def test_different_paths_cached_independently(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT = 60
        call_count = {"a": 0, "b": 0}

        def get_response(request):
            call_count[request.path.strip("/")] += 1
            return make_html_response(f"<p>{request.path}</p>")

        middleware = MarkdownMiddleware(get_response)
        middleware(rf.get("/a/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/b/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/a/", HTTP_ACCEPT="text/markdown"))
        assert call_count["a"] == 1
        assert call_count["b"] == 1

    def test_no_caching_without_setting(self, rf):
        call_count = 0

        def get_response(request):
            nonlocal call_count
            call_count += 1
            return make_html_response()

        middleware = MarkdownMiddleware(get_response)
        middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/", HTTP_ACCEPT="text/markdown"))
        assert call_count == 2

    def test_get_path_cache_key_is_deterministic(self, rf):
        middleware = make_middleware()
        assert middleware.get_path_cache_key(rf.get("/page/")) == middleware.get_path_cache_key(
            rf.get("/page/")
        )

    def test_get_path_cache_key_differs_by_path(self, rf):
        middleware = make_middleware()
        assert middleware.get_path_cache_key(rf.get("/a/")) != middleware.get_path_cache_key(
            rf.get("/b/")
        )

    def test_get_full_cache_key_always_returns_key(self, rf):
        middleware = make_middleware()
        assert middleware.get_full_cache_key(rf.get("/some/path/")) is not None

    def test_get_full_cache_key_differs_by_query_string(self, rf):
        middleware = make_middleware()
        key_foo = middleware.get_full_cache_key(rf.get("/page/", {"q": "foo"}))
        key_bar = middleware.get_full_cache_key(rf.get("/page/", {"q": "bar"}))
        assert key_foo != key_bar

    def test_get_full_cache_key_same_path_shares_token(self, rf):
        middleware = make_middleware()
        key_a = middleware.get_full_cache_key(rf.get("/page/"))
        key_b = middleware.get_full_cache_key(rf.get("/page/"))
        assert key_a == key_b

    def test_get_full_cache_key_changes_after_invalidation(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT = 60
        middleware = make_middleware()
        key_before = middleware.get_full_cache_key(rf.get("/page/"))
        invalidate_cache("/page/")
        key_after = middleware.get_full_cache_key(rf.get("/page/"))
        assert key_before != key_after

    def test_anonymous_only_default_allows_anonymous(self, rf):
        middleware = make_middleware()
        request = rf.get("/", HTTP_ACCEPT="text/markdown")
        request.user = type("User", (), {"is_authenticated": False})()
        response = middleware(request)
        assert "text/markdown" in response["Content-Type"]

    def test_anonymous_only_blocks_authenticated(self, rf):
        middleware = make_middleware()
        request = rf.get("/", HTTP_ACCEPT="text/markdown")
        request.user = type("User", (), {"is_authenticated": True})()
        response = middleware(request)
        assert response["Content-Type"] == "text/html; charset=utf-8"

    def test_anonymous_only_false_allows_authenticated(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_ANONYMOUS_ONLY = False
        middleware = make_middleware()
        request = rf.get("/", HTTP_ACCEPT="text/markdown")
        request.user = type("User", (), {"is_authenticated": True})()
        response = middleware(request)
        assert "text/markdown" in response["Content-Type"]

    def test_anonymous_only_false_allows_anonymous(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_ANONYMOUS_ONLY = False
        middleware = make_middleware()
        request = rf.get("/", HTTP_ACCEPT="text/markdown")
        request.user = type("User", (), {"is_authenticated": False})()
        response = middleware(request)
        assert "text/markdown" in response["Content-Type"]

    def test_invalidate_cache_removes_all_query_string_variants(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT = 60
        call_count = 0

        def get_response(request):
            nonlocal call_count
            call_count += 1
            return make_html_response()

        middleware = MarkdownMiddleware(get_response)
        middleware(rf.get("/page/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/page/", {"q": "one"}, HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/page/", {"q": "two"}, HTTP_ACCEPT="text/markdown"))
        assert call_count == 3

        invalidate_cache("/page/")

        middleware(rf.get("/page/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/page/", {"q": "one"}, HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/page/", {"q": "two"}, HTTP_ACCEPT="text/markdown"))
        assert call_count == 6

    def test_invalidate_cache_does_not_affect_other_paths(self, rf, settings):
        settings.MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT = 60
        call_count = {"a": 0, "b": 0}

        def get_response(request):
            key = request.path.strip("/")
            call_count[key] += 1
            return make_html_response(f"<p>{request.path}</p>")

        middleware = MarkdownMiddleware(get_response)
        middleware(rf.get("/a/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/b/", HTTP_ACCEPT="text/markdown"))

        invalidate_cache("/a/")

        middleware(rf.get("/a/", HTTP_ACCEPT="text/markdown"))
        middleware(rf.get("/b/", HTTP_ACCEPT="text/markdown"))
        assert call_count["a"] == 2
        assert call_count["b"] == 1

    def test_invalidate_cache_on_unknown_path_is_safe(self):
        # Should not raise even if the path was never cached
        invalidate_cache("/never/cached/")
