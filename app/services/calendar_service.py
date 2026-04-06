from googleapiclient.discovery import build
from datetime import datetime, timedelta
from app.services.google_auth import get_google_credentials
import pytz


async def get_calendar_service(user_id: str):
    creds = await get_google_credentials(user_id)
    if not creds:
        raise ValueError("No Google credentials found. User needs to connect Google account.")
    return build("calendar", "v3", credentials=creds)


async def list_events(
    user_id: str,
    time_min: str,
    time_max: str,
    max_results: int = 20,
) -> list[dict]:
    """List events in a time range. Returns simplified event objects."""
    service = await get_calendar_service(user_id)
    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for event in result.get("items", []):
        events.append({
            "id": event["id"],
            "summary": event.get("summary", "(No title)"),
            "start": event["start"].get("dateTime", event["start"].get("date")),
            "end": event["end"].get("dateTime", event["end"].get("date")),
            "location": event.get("location", ""),
            "description": event.get("description", ""),
            "attendees": [
                {"email": a["email"], "status": a.get("responseStatus", "needsAction")}
                for a in event.get("attendees", [])
            ],
        })
    return events


async def check_freebusy(
    user_id: str,
    calendars: list[str],
    time_min: str,
    time_max: str,
) -> dict:
    """Check free/busy status for one or more calendars."""
    service = await get_calendar_service(user_id)

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "timeZone": "UTC",
        "items": [{"id": cal} for cal in calendars],
    }

    result = service.freebusy().query(body=body).execute()

    freebusy_data = {}
    for email in calendars:
        cal_data = result["calendars"].get(email, {})
        errors = cal_data.get("errors", [])
        busy = cal_data.get("busy", [])

        if errors:
            freebusy_data[email] = {
                "accessible": False,
                "busy": [],
                "error": errors[0].get("reason", "unknown"),
            }
        else:
            freebusy_data[email] = {
                "accessible": True,
                "busy": busy,
            }

    return freebusy_data


async def create_event(
    user_id: str,
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    attendees: list[str] = None,
    send_updates: str = "all",
    add_meet_link: bool = False,
) -> dict:
    """Create a calendar event with optional attendees and Google Meet link."""
    service = await get_calendar_service(user_id)

    event_body = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"},
        "description": description,
        "location": location,
    }

    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]

    if add_meet_link:
        event_body["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet-{datetime.now().timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    result = service.events().insert(
        calendarId="primary",
        body=event_body,
        sendUpdates=send_updates,
        conferenceDataVersion=1 if add_meet_link else 0,
    ).execute()

    return {
        "id": result["id"],
        "summary": result.get("summary"),
        "start": result["start"].get("dateTime"),
        "end": result["end"].get("dateTime"),
        "html_link": result.get("htmlLink"),
        "meet_link": result.get("hangoutLink", ""),
    }


async def update_event(
    user_id: str,
    event_id: str,
    updates: dict,
    send_updates: str = "all",
    add_meet_link: bool = False,
) -> dict:
    """Update an existing calendar event."""
    service = await get_calendar_service(user_id)

    event = service.events().get(calendarId="primary", eventId=event_id).execute()

    if "summary" in updates:
        event["summary"] = updates["summary"]
    if "start_time" in updates:
        event["start"] = {"dateTime": updates["start_time"], "timeZone": "UTC"}
    if "end_time" in updates:
        event["end"] = {"dateTime": updates["end_time"], "timeZone": "UTC"}
    if "description" in updates:
        event["description"] = updates["description"]
    if "location" in updates:
        event["location"] = updates["location"]
    if "attendees" in updates:
        existing = event.get("attendees", [])
        existing_emails = {a["email"] for a in existing}
        for email in updates["attendees"]:
            if email not in existing_emails:
                existing.append({"email": email})
        event["attendees"] = existing
    if add_meet_link and "conferenceData" not in event:
        event["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet-{event_id}-{datetime.now().timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    result = service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event,
        sendUpdates=send_updates,
        conferenceDataVersion=1 if add_meet_link else 0,
    ).execute()

    return {
        "id": result["id"],
        "summary": result.get("summary"),
        "start": result["start"].get("dateTime"),
        "end": result["end"].get("dateTime"),
        "meet_link": result.get("hangoutLink", ""),
    }


async def delete_event(
    user_id: str,
    event_id: str,
    send_updates: str = "all",
) -> bool:
    """Delete a calendar event."""
    service = await get_calendar_service(user_id)
    service.events().delete(
        calendarId="primary",
        eventId=event_id,
        sendUpdates=send_updates,
    ).execute()
    return True


async def find_available_slots(
    user_id: str,
    date_start: str,
    date_end: str,
    duration_minutes: int,
    earliest_hour: int = 8,
    latest_hour: int = 21,
    timezone: str = None,
) -> list[dict]:
    """Find available time slots in user's calendar."""
    if not timezone:
        from app.db.users import get_user
        user = await get_user(user_id)
        timezone = user.get("timezone", "America/Los_Angeles")

    tz = pytz.timezone(timezone)
    start_dt = tz.localize(datetime.strptime(date_start, "%Y-%m-%d").replace(hour=0, minute=0))
    end_dt = tz.localize(datetime.strptime(date_end, "%Y-%m-%d").replace(hour=23, minute=59))

    from app.db.client import supabase as sb
    account = sb.table("linked_accounts").select("email").eq("user_id", user_id).eq("provider", "google").execute()
    user_email = account.data[0]["email"] if account.data else "primary"

    freebusy = await check_freebusy(
        user_id,
        calendars=[user_email],
        time_min=start_dt.isoformat(),
        time_max=end_dt.isoformat(),
    )

    cal_data = freebusy.get(user_email, {})
    busy_periods = cal_data.get("busy", []) if isinstance(cal_data, dict) else []

    slots = []
    current = start_dt.replace(hour=earliest_hour, minute=0)

    while current < end_dt:
        if current.hour >= latest_hour:
            current = (current + timedelta(days=1)).replace(hour=earliest_hour, minute=0)
            continue

        slot_end = current + timedelta(minutes=duration_minutes)

        is_free = True
        for busy in busy_periods:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00")).astimezone(tz)
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00")).astimezone(tz)

            if current < busy_end and slot_end > busy_start:
                is_free = False
                break

        if is_free and slot_end.hour <= latest_hour:
            slots.append({
                "start": current.isoformat(),
                "end": slot_end.isoformat(),
                "label": current.strftime("%A %b %d, %I:%M %p"),
            })

        current += timedelta(minutes=30)

    return slots
