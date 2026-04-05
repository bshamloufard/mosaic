TOOL_DEFINITIONS = [
    {
        "name": "resolve_contact",
        "description": (
            "Search the user's Google Contacts to find a person's email address by name. "
            "Use this BEFORE any scheduling operation that involves other people. "
            "The search is prefix-based: 'Bha' will match 'Bharat Mekala'. "
            "If multiple matches are found, present ALL options to the user and ask which one they mean. "
            "If no match is found, ask the user for the person's email address directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The person's name or partial name to search for. E.g., 'Bharat' or 'Sarah Johnson'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_calendar_events",
        "description": (
            "List the user's calendar events within a date range. "
            "Use this to show the user their schedule, check what's coming up, "
            "or understand their current commitments before suggesting new times. "
            "Always call this BEFORE creating or modifying events to understand current schedule context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format. E.g., '2025-01-15'"
                },
                "date_end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format. E.g., '2025-01-17'"
                }
            },
            "required": ["date_start", "date_end"]
        }
    },
    {
        "name": "check_availability",
        "description": (
            "Check free/busy status for one or more people's Google Calendars. "
            "Pass email addresses of people to check. This uses the Google FreeBusy API. "
            "IMPORTANT: If a calendar is not accessible (the person hasn't shared it), "
            "the result will show accessible=false. In that case, tell the user you can't "
            "see that person's calendar and offer to send an availability poll email instead. "
            "An empty busy list with accessible=true means the person IS free. "
            "An empty busy list with accessible=false means you COULDN'T CHECK."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "emails": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email addresses to check availability for"
                },
                "date_start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "date_end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format"
                }
            },
            "required": ["emails", "date_start", "date_end"]
        }
    },
    {
        "name": "find_open_slots",
        "description": (
            "Find available time slots in the user's OWN calendar within a date range. "
            "Use this when you need to suggest times for new events. "
            "You can filter by earliest/latest acceptable hours (e.g., 9-17 for work hours, "
            "6-8 or 17-20 for gym, 10-17 for outdoor activities). "
            "Returns a list of available slots with human-readable labels."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "date_end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "How long the event should be, in minutes",
                    "minimum": 15,
                    "maximum": 480
                },
                "earliest_hour": {
                    "type": "integer",
                    "description": "Earliest acceptable start hour (0-23). E.g., 9 for 9am.",
                    "minimum": 0,
                    "maximum": 23,
                    "default": 8
                },
                "latest_hour": {
                    "type": "integer",
                    "description": "Latest acceptable start hour (0-23). E.g., 17 for 5pm.",
                    "minimum": 0,
                    "maximum": 23,
                    "default": 21
                }
            },
            "required": ["date_start", "date_end", "duration_minutes"]
        }
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Create a new event on the user's Google Calendar. "
            "CRITICAL: NEVER call this without first confirming with the user. "
            "Always present the event details and ask 'Should I go ahead?' BEFORE calling this tool. "
            "Wait for the user to say 'yes', 'confirm', 'go ahead', etc. "
            "Only call this tool AFTER the user has explicitly confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Event title. E.g., 'Pickleball with Bharat, Tej, and Adil'"
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format with timezone. E.g., '2025-01-15T14:00:00-08:00'"
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format with timezone. E.g., '2025-01-15T15:30:00-08:00'"
                },
                "description": {
                    "type": "string",
                    "description": "Event description. Can include HTML: <b>, <br>, <ul>, <li>, <a>.",
                    "default": ""
                },
                "location": {
                    "type": "string",
                    "description": "Event location. E.g., 'Mission Bay Courts, SF'",
                    "default": ""
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee email addresses.",
                    "default": []
                },
                "add_meet_link": {
                    "type": "boolean",
                    "description": "Whether to add a Google Meet video call link",
                    "default": False
                }
            },
            "required": ["summary", "start_time", "end_time"]
        }
    },
    {
        "name": "update_calendar_event",
        "description": (
            "Update an existing calendar event. Use this when the user wants to reschedule, "
            "rename, or change details of an event. You need the event_id which you can get "
            "from list_calendar_events. ALWAYS confirm changes with the user before executing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The Google Calendar event ID (from list_calendar_events)"
                },
                "summary": {"type": "string", "description": "New event title (optional)"},
                "start_time": {"type": "string", "description": "New start time in ISO 8601 (optional)"},
                "end_time": {"type": "string", "description": "New end time in ISO 8601 (optional)"},
                "description": {"type": "string", "description": "New description (optional)"},
                "location": {"type": "string", "description": "New location (optional)"}
            },
            "required": ["event_id"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": (
            "Delete/cancel a calendar event. ALWAYS confirm with the user first. "
            "This will also notify attendees that the event has been cancelled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The Google Calendar event ID to delete"
                }
            },
            "required": ["event_id"]
        }
    },
    {
        "name": "send_email",
        "description": (
            "Send an email on behalf of the user via Gmail. Use this for: "
            "1) Sending availability polls to people whose calendars you can't access. "
            "2) Sending meeting confirmations or updates. "
            "3) Any email coordination the user requests. "
            "ALWAYS confirm the email content with the user before sending. "
            "The email is sent FROM the user's Gmail account."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Email body in plain text (will be converted to HTML)"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "send_availability_poll",
        "description": (
            "Send an availability poll to one or more people when you can't access their calendars. "
            "This creates a web-based poll page and sends an email with a link to it. "
            "Use this when check_availability returns accessible=false for someone. "
            "The poll lets recipients pick from proposed times or suggest alternatives."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_title": {
                    "type": "string",
                    "description": "What the event is. E.g., 'Pickleball'"
                },
                "participants": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"}
                        },
                        "required": ["name", "email"]
                    },
                    "description": "List of people to send the poll to"
                },
                "proposed_times": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "description": "ISO 8601 datetime"},
                            "end": {"type": "string", "description": "ISO 8601 datetime"},
                            "label": {"type": "string", "description": "Human-readable label"}
                        },
                        "required": ["start", "end", "label"]
                    },
                    "description": "Proposed time slots for the poll"
                }
            },
            "required": ["event_title", "participants", "proposed_times"]
        }
    },
]
