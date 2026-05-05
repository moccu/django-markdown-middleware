django-markdown-middleware
==========================

.. image:: https://img.shields.io/pypi/v/django-markdown-middleware.svg
   :target: https://pypi.org/project/django-markdown-middleware/
   :alt: Latest Version

.. image:: https://github.com/moccu/django-markdown-middleware/workflows/Test/badge.svg?branch=master
   :target: https://github.com/moccu/django-markdown-middleware/actions?workflow=Test
   :alt: CI Status


A Django middleware that converts HTML responses to Markdown when the client
sends an ``Accept: text/markdown`` request header.


Requirements
------------

django-markdown-middleware supports Python 3.11+ and requires Django 5.2 or later.


Installation
------------

.. code-block:: shell

    $ pip install django-markdown-middleware

Add the middleware to your Django settings:

.. code-block:: python

    MIDDLEWARE = [
        ...
        "markdown_middleware.middleware.MarkdownMiddleware",
        ...
    ]

The middleware must be placed **after** any middleware that sets the response
content type (e.g. after ``CommonMiddleware``).


Usage
-----

Any client that sends ``Accept: text/markdown`` in the request headers will
receive the HTML response body converted to Markdown, with the response
``Content-Type`` changed to ``text/markdown; charset=utf-8``.

The response also includes an ``X-Markdown-Tokens`` header containing an
approximate token count of the converted Markdown content (estimated as
``len(markdown) // 4``).

Only HTTP 200 responses with a ``text/html`` content type are converted.
All other responses are passed through unchanged.


Caching
-------

To enable caching of converted Markdown responses, set
``MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT`` in your Django settings to the desired
cache duration in seconds:

.. code-block:: python

    # Cache converted Markdown responses for 5 minutes
    MARKDOWN_MIDDLEWARE_CACHE_TIMEOUT = 300

When this setting is absent or ``None``, no caching is performed.

Cache keys have the form ``markdown_middleware:<path>``, for example
``markdown_middleware:/api/products/``, making them easy to inspect or
manage directly in your cache backend.


Cache Invalidation
------------------

To invalidate cached Markdown responses for a specific path, use
``invalidate_cache``. It removes all cached variants of that path,
including responses with different query strings:

.. code-block:: python

    from markdown_middleware import invalidate_cache

    # Invalidates /blog/my-post/, /blog/my-post/?page=2, etc.
    invalidate_cache("/blog/my-post/")

This is useful in post-save signals or management commands when content
changes and the cached Markdown must be refreshed.


Prepare for development
-----------------------

Install `uv <https://docs.astral.sh/uv/>`_, then:

.. code-block:: shell

    $ uv sync --group dev

Run the tests:

.. code-block:: shell

    $ make tests
