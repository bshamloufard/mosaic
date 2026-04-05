from app.db.client import supabase


async def save_message(conversation_id: str, role: str, content: str) -> dict:
    """Save a message to the database."""
    token_count = len(content) // 4

    result = supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "token_count": token_count,
    }).execute()

    return result.data[0]


async def get_recent_messages(conversation_id: str, limit: int = 10) -> list[dict]:
    """Get the most recent messages for a conversation, ordered chronologically."""
    result = supabase.table("messages")\
        .select("role, content, created_at")\
        .eq("conversation_id", conversation_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    return list(reversed(result.data))


async def get_total_token_count(conversation_id: str) -> int:
    """Get total estimated tokens for all messages in a conversation."""
    result = supabase.table("messages")\
        .select("token_count")\
        .eq("conversation_id", conversation_id)\
        .execute()

    return sum(m.get("token_count", 0) for m in result.data)


async def delete_old_messages(conversation_id: str, keep_recent: int = 10) -> int:
    """Delete messages older than the N most recent."""
    recent = supabase.table("messages")\
        .select("id")\
        .eq("conversation_id", conversation_id)\
        .order("created_at", desc=True)\
        .limit(keep_recent)\
        .execute()

    recent_ids = [m["id"] for m in recent.data]

    if recent_ids:
        supabase.table("messages")\
            .delete()\
            .eq("conversation_id", conversation_id)\
            .not_.in_("id", recent_ids)\
            .execute()

    return len(recent_ids)
