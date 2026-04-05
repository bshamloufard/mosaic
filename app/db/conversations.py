from app.db.client import supabase


async def get_or_create_conversation(user_id: str, chat_id: str) -> dict:
    result = supabase.table("conversations").select("*").eq("user_id", user_id).execute()
    if result.data:
        conv = result.data[0]
        if chat_id and conv.get("linq_chat_id") != chat_id:
            supabase.table("conversations").update({"linq_chat_id": chat_id}).eq("id", conv["id"]).execute()
            conv["linq_chat_id"] = chat_id
        return conv
    new_conv = supabase.table("conversations").insert({
        "user_id": user_id,
        "linq_chat_id": chat_id,
    }).execute()
    return new_conv.data[0]


async def update_summary(conversation_id: str, summary: str):
    supabase.table("conversations").update({
        "summary": summary,
        "summary_token_count": len(summary) // 4,
    }).eq("id", conversation_id).execute()
