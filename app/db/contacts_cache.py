from app.db.client import supabase


async def search_cached_contacts(user_id: str, query: str, limit: int = 5) -> list[dict]:
    """Search contacts cache by display name (case-insensitive partial match)."""
    result = supabase.table("contacts_cache")\
        .select("display_name, email, phone")\
        .eq("user_id", user_id)\
        .ilike("display_name", f"%{query}%")\
        .limit(limit)\
        .execute()
    return result.data


async def upsert_cached_contact(user_id: str, display_name: str, email: str, phone: str = "", source: str = "google_contacts"):
    """Add or update a contact in the cache."""
    if not email:
        return
    supabase.table("contacts_cache").upsert(
        {
            "user_id": user_id,
            "display_name": display_name,
            "email": email,
            "phone": phone,
            "source": source,
        },
        on_conflict="user_id,email"
    ).execute()


async def increment_interaction_count(user_id: str, email: str):
    """Bump interaction count when a contact is used in scheduling."""
    result = supabase.table("contacts_cache")\
        .select("id, interaction_count")\
        .eq("user_id", user_id)\
        .eq("email", email)\
        .execute()
    if result.data:
        current = result.data[0].get("interaction_count", 0)
        supabase.table("contacts_cache")\
            .update({"interaction_count": current + 1})\
            .eq("id", result.data[0]["id"])\
            .execute()


async def get_frequent_contacts(user_id: str, limit: int = 10) -> list[dict]:
    """Get the user's most frequently referenced contacts."""
    result = supabase.table("contacts_cache")\
        .select("display_name, email, phone, interaction_count")\
        .eq("user_id", user_id)\
        .order("interaction_count", desc=True)\
        .limit(limit)\
        .execute()
    return result.data
