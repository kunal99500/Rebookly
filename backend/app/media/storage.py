"""Uploads and deletes files in Supabase Storage. Only the backend talks to Storage, using the secret key."""
import httpx


class StorageError(Exception):
    pass


class SupabaseStorage:
    def __init__(self, supabase_url: str, secret_key: str, timeout: float = 30.0):
        if not supabase_url or not secret_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for storage")
        self._base = f"{supabase_url.rstrip('/')}/storage/v1"
        headers = {"apikey": secret_key}
        if secret_key.startswith("eyJ"):  # legacy service_role keys are JWTs and also go in Authorization
            headers["Authorization"] = f"Bearer {secret_key}"
        self._http = httpx.AsyncClient(headers=headers, timeout=timeout)

    async def close(self) -> None:
        await self._http.aclose()

    def public_url(self, bucket: str, path: str) -> str:
        return f"{self._base}/object/public/{bucket}/{path}"

    async def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        response = await self._http.post(
            f"{self._base}/object/{bucket}/{path}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "false", "Cache-Control": "max-age=31536000"},
        )
        if response.status_code >= 400:
            raise StorageError(f"Upload failed ({response.status_code}): {response.text[:200]}")

    async def delete(self, bucket: str, paths: list[str]) -> None:
        if not paths:
            return
        response = await self._http.request("DELETE", f"{self._base}/object/{bucket}", json={"prefixes": paths})
        if response.status_code >= 400:
            raise StorageError(f"Delete failed ({response.status_code}): {response.text[:200]}")