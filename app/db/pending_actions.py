from app.db.client import supabase


async def get_pending_actions(conversation_id: str) -> list:
    result = supabase.table("pending_actions")\
        .select("*")\
        .eq("conversation_id", conversation_id)\
        .eq("status", "pending")\
        .execute()
    return result.data


async def create_pending_action(conversation_id: str, action_type: str, payload: dict) -> dict:
    result = supabase.table("pending_actions").insert({
        "conversation_id": conversation_id,
        "action_type": action_type,
        "action_payload": payload,
    }).execute()
    return result.data[0]


async def update_action_status(action_id: str, status: str):
    supabase.table("pending_actions").update({"status": status}).eq("id", action_id).execute()
