"""Removing a sign-in account from Supabase Auth (server-side, with the service role key)."""
import httpx


class AuthAdminError(Exception):
    pass


async def delete_auth_user(supabase_url: str, service_role_key: str, user_id) -> None:
    """Delete the Supabase sign-in account. A missing account (already deleted) counts as done."""
    async with httpx.AsyncClient(timeout=15) as http:
        response = await http.delete(
            f"{supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
            headers={"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"})
    if response.status_code not in (200, 204, 404):
        raise AuthAdminError(f"Supabase returned {response.status_code}")