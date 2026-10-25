"""Tests for the Supabase Storage client (no network)."""
import json

import httpx
import pytest

from app.media.storage import StorageError, SupabaseStorage


def make_storage(handler, key="sb_secret_abc"):
    storage = SupabaseStorage("https://proj.supabase.co", key)
    storage._http = httpx.AsyncClient(headers=storage._http.headers, transport=httpx.MockTransport(handler))
    return storage


def test_public_url():
    storage = SupabaseStorage("https://proj.supabase.co/", "sb_secret_abc")
    assert storage.public_url("business-photos", "b1/p1.webp") == \
        "https://proj.supabase.co/storage/v1/object/public/business-photos/b1/p1.webp"


def test_new_secret_key_goes_only_in_apikey_header():
    headers = SupabaseStorage("https://proj.supabase.co", "sb_secret_abc")._http.headers
    assert headers["apikey"] == "sb_secret_abc" and "authorization" not in headers


def test_legacy_jwt_key_also_goes_in_authorization():
    headers = SupabaseStorage("https://proj.supabase.co", "eyJhbGciOi.legacy")._http.headers
    assert headers["authorization"] == "Bearer eyJhbGciOi.legacy"


@pytest.mark.asyncio
async def test_upload_sends_file_to_bucket_path():
    seen = {}

    def handler(request: httpx.Request):
        seen.update(path=request.url.path, type=request.headers["content-type"], body=request.content)
        return httpx.Response(200, json={"Key": "ok"})

    storage = make_storage(handler)
    await storage.upload("business-photos", "b1/p1.webp", b"IMG", "image/webp")
    assert seen == {"path": "/storage/v1/object/business-photos/b1/p1.webp", "type": "image/webp", "body": b"IMG"}


@pytest.mark.asyncio
async def test_delete_sends_all_paths():
    seen = {}

    def handler(request: httpx.Request):
        seen.update(method=request.method, body=json.loads(request.content))
        return httpx.Response(200, json=[])

    storage = make_storage(handler)
    await storage.delete("business-photos", ["a.webp", "b.webp"])
    assert seen == {"method": "DELETE", "body": {"prefixes": ["a.webp", "b.webp"]}}


@pytest.mark.asyncio
async def test_errors_are_raised():
    storage = make_storage(lambda request: httpx.Response(403, json={"error": "Unauthorized"}))
    with pytest.raises(StorageError):
        await storage.upload("business-photos", "x.webp", b"IMG", "image/webp")


def test_missing_settings_are_refused():
    with pytest.raises(ValueError):
        SupabaseStorage("", "")