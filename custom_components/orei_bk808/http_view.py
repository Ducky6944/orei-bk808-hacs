"""Serve the bundled static cover art over the Home Assistant HTTP server.

This is what makes the media-control card show a real image instead of HA's
empty placeholder. The image lives in this integration's `static/` directory,
so users can swap it for their own (drop in `static/cover.jpg`) without any
code change.

Registered from `async_setup_entry` via `hass.http.register_view(...)` (the
`http` integration is already an `after_dependency`, so `hass.http` exists).
"""

import mimetypes
from pathlib import Path

from aiohttp import web

# HomeAssistantView moved from `homeassistant.components.http` to
# `homeassistant.helpers.http` in recent builds; prefer the new location and
# fall back to the old one so we keep working across HA versions.
try:
    from homeassistant.helpers.http import HomeAssistantView  # type: ignore
except ImportError:  # pragma: no cover - older builds
    from homeassistant.components.http import HomeAssistantView  # type: ignore

_URL = "/local/orei_bk808/cover.jpg"
_STATIC = Path(__file__).parent / "static" / "cover.jpg"


class OreiCoverView(HomeAssistantView):
    """Serve only the bundled cover image. Unauthenticated + CORS-open so
    the media-control card (which loads it as a plain <img>) always renders."""

    # `name` is required by HomeAssistantView.register_view (aiohttp uses it
    # to name the route). `url` alone is not enough — without `name` setup
    # raises and the route is silently never added.
    name = "orei_bk808_cover"
    url = _URL
    extra_urls = []
    requires_auth = False
    cors_allowed = True

    def get(self, request: web.Request) -> web.Response:
        try:
            data = _STATIC.read_bytes()
        except OSError:
            return web.Response(status=404, text="cover not found")
        content_type = mimetypes.guess_type(_STATIC.name)[0] or "image/jpeg"
        return web.Response(
            body=data,
            content_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )
