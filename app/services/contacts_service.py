from googleapiclient.discovery import build
from app.services.google_auth import get_google_credentials
from app.db.client import supabase


async def search_contacts(user_id: str, query: str, max_results: int = 5) -> list[dict]:
    """
    Search user's Google Contacts by name.
    Returns list of {name, email, phone, source}.
    """
    cache_results = supabase.table("contacts_cache")\
        .select("display_name, email, phone")\
        .eq("user_id", user_id)\
        .ilike("display_name", f"%{query}%")\
        .limit(max_results)\
        .execute()

    if cache_results.data and len(cache_results.data) > 0:
        return cache_results.data

    creds = await get_google_credentials(user_id)
    if not creds:
        return []

    service = build("people", "v1", credentials=creds)

    try:
        service.people().searchContacts(
            query="",
            readMask="names,emailAddresses,phoneNumbers"
        ).execute()
    except Exception:
        pass

    try:
        results = service.people().searchContacts(
            query=query,
            pageSize=max_results,
            readMask="names,emailAddresses,phoneNumbers"
        ).execute()
    except Exception:
        try:
            results = service.otherContacts().search(
                query=query,
                pageSize=max_results,
                readMask="names,emailAddresses,phoneNumbers"
            ).execute()
        except Exception:
            return []

    contacts = []
    for person in results.get("results", []):
        p = person.get("person", {})
        name = ""
        email = ""
        phone = ""

        names = p.get("names", [])
        if names:
            name = names[0].get("displayName", "")

        emails = p.get("emailAddresses", [])
        if emails:
            email = emails[0].get("value", "")

        phones = p.get("phoneNumbers", [])
        if phones:
            phone = phones[0].get("value", "")

        if name or email:
            contacts.append({"display_name": name, "email": email, "phone": phone})

            supabase.table("contacts_cache").upsert(
                {
                    "user_id": user_id,
                    "display_name": name,
                    "email": email,
                    "phone": phone,
                    "source": "google_contacts",
                },
                on_conflict="user_id,email"
            ).execute()

    return contacts


async def sync_contacts_to_cache(user_id: str) -> int:
    """Full sync of user's Google Contacts to local cache."""
    creds = await get_google_credentials(user_id)
    if not creds:
        return 0

    service = build("people", "v1", credentials=creds)
    count = 0
    page_token = None

    while True:
        results = service.people().connections().list(
            resourceName="people/me",
            pageSize=100,
            personFields="names,emailAddresses,phoneNumbers",
            pageToken=page_token,
        ).execute()

        for person in results.get("connections", []):
            name = ""
            email = ""
            phone = ""

            names = person.get("names", [])
            if names:
                name = names[0].get("displayName", "")

            emails = person.get("emailAddresses", [])
            if emails:
                email = emails[0].get("value", "")

            phones = person.get("phoneNumbers", [])
            if phones:
                phone = phones[0].get("value", "")

            if email:
                supabase.table("contacts_cache").upsert(
                    {
                        "user_id": user_id,
                        "display_name": name,
                        "email": email,
                        "phone": phone,
                        "source": "google_contacts",
                    },
                    on_conflict="user_id,email"
                ).execute()
                count += 1

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return count
