import json
import uuid
from app.services import calendar_service, gmail_service, contacts_service
from app.services.smart_time import get_activity_profile, rank_time_slots
from app.db.pending_actions import create_pending_action
from app.db.client import supabase


async def execute_tool(tool_name: str, tool_input: dict, user_id: str, conversation_id: str) -> dict:
    """Route tool calls to their implementations."""

    if tool_name == "resolve_contact":
        contacts = await contacts_service.search_contacts(user_id, tool_input["query"])
        if not contacts:
            return {"found": False, "message": f"No contacts found matching '{tool_input['query']}'"}
        return {"found": True, "contacts": contacts}

    elif tool_name == "list_calendar_events":
        from datetime import datetime
        import pytz
        from app.db.users import get_user
        user = await get_user(user_id)
        user_tz = user.get("timezone", "America/Los_Angeles")
        tz = pytz.timezone(user_tz)
        start = tz.localize(datetime.strptime(tool_input["date_start"], "%Y-%m-%d"))
        end = tz.localize(datetime.strptime(tool_input["date_end"], "%Y-%m-%d").replace(hour=23, minute=59))
        events = await calendar_service.list_events(user_id, start.isoformat(), end.isoformat())
        return {"events": events, "count": len(events)}

    elif tool_name == "check_availability":
        from datetime import datetime
        import pytz
        from app.db.users import get_user
        user = await get_user(user_id)
        user_tz = user.get("timezone", "America/Los_Angeles")
        tz = pytz.timezone(user_tz)
        start = tz.localize(datetime.strptime(tool_input["date_start"], "%Y-%m-%d"))
        end = tz.localize(datetime.strptime(tool_input["date_end"], "%Y-%m-%d").replace(hour=23, minute=59))
        result = await calendar_service.check_freebusy(
            user_id, tool_input["emails"], start.isoformat(), end.isoformat()
        )
        return result

    elif tool_name == "find_open_slots":
        slots = await calendar_service.find_available_slots(
            user_id,
            tool_input["date_start"],
            tool_input["date_end"],
            tool_input["duration_minutes"],
            tool_input.get("earliest_hour", 8),
            tool_input.get("latest_hour", 21),
        )
        return {"available_slots": slots[:10], "total_found": len(slots)}

    elif tool_name == "create_calendar_event":
        result = await calendar_service.create_event(
            user_id,
            summary=tool_input["summary"],
            start_time=tool_input["start_time"],
            end_time=tool_input["end_time"],
            description=tool_input.get("description", ""),
            location=tool_input.get("location", ""),
            attendees=tool_input.get("attendees", []),
            add_meet_link=tool_input.get("add_meet_link", False),
        )
        return {"success": True, "event": result}

    elif tool_name == "update_calendar_event":
        updates = {}
        for key in ["summary", "start_time", "end_time", "description", "location"]:
            if key in tool_input and tool_input[key]:
                updates[key] = tool_input[key]
        result = await calendar_service.update_event(user_id, tool_input["event_id"], updates)
        return {"success": True, "event": result}

    elif tool_name == "delete_calendar_event":
        await calendar_service.delete_event(user_id, tool_input["event_id"])
        return {"success": True, "message": "Event deleted and attendees notified."}

    elif tool_name == "send_email":
        result = await gmail_service.send_email(
            user_id,
            to=tool_input["to"],
            subject=tool_input["subject"],
            body_html=f"<p>{tool_input['body']}</p>",
        )
        return {"success": True, "message_id": result["message_id"]}

    elif tool_name == "send_availability_poll":
        poll_id = str(uuid.uuid4())
        from app.db.users import get_user
        user = await get_user(user_id)

        supabase.table("polls").insert({
            "id": poll_id,
            "user_id": user_id,
            "title": tool_input["event_title"],
            "proposed_times": tool_input["proposed_times"],
            "participants": tool_input["participants"],
            "status": "open",
        }).execute()

        results = []
        for participant in tool_input["participants"]:
            email_result = await gmail_service.send_availability_email(
                user_id=user_id,
                to_email=participant["email"],
                to_name=participant["name"],
                user_name=user.get("display_name", "Someone"),
                event_title=tool_input["event_title"],
                poll_id=poll_id,
                proposed_times=tool_input["proposed_times"],
            )
            results.append({
                "name": participant["name"],
                "email": participant["email"],
                "sent": True,
            })

        from app.config import settings
        return {
            "success": True,
            "poll_id": poll_id,
            "emails_sent": results,
            "poll_url": f"{settings.app_base_url}/poll/{poll_id}",
        }

    else:
        return {"error": f"Unknown tool: {tool_name}"}
