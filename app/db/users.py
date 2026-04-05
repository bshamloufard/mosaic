from app.db.client import supabase


async def get_or_create_user(phone: str) -> dict:
    result = supabase.table("users").select("*").eq("phone_number", phone).execute()
    if result.data:
        return result.data[0]
    new_user = supabase.table("users").insert({"phone_number": phone}).execute()
    return new_user.data[0]


async def get_user(user_id: str) -> dict:
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        return {"timezone": "America/Los_Angeles", "display_name": "there"}
    return result.data[0]


async def get_user_by_phone(phone: str) -> dict | None:
    result = supabase.table("users").select("*").eq("phone_number", phone).execute()
    return result.data[0] if result.data else None


async def update_user(user_id: str, updates: dict) -> dict:
    result = supabase.table("users").update(updates).eq("id", user_id).execute()
    return result.data[0] if result.data else {}
