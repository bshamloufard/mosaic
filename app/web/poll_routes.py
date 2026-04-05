from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.db.client import supabase

poll_router = APIRouter()


@poll_router.get("/{poll_id}")
async def view_poll(poll_id: str):
    """Render the availability poll page."""
    poll_result = supabase.table("polls").select("*").eq("id", poll_id).execute()

    if not poll_result.data:
        return HTMLResponse("<h1>Poll not found</h1>", status_code=404)

    p = poll_result.data[0]
    times_html = ""
    for i, t in enumerate(p["proposed_times"]):
        times_html += f"""
        <label style="display: block; padding: 12px; margin: 8px 0; background: #f5f5f7; border-radius: 8px; cursor: pointer;">
            <input type="checkbox" name="times" value="{i}" style="margin-right: 8px;">
            {t['label']}
        </label>
        """

    return HTMLResponse(f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Pick a time — {p['title']}</title>
    </head>
    <body style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2>📅 {p['title']}</h2>
        <p>Select all times that work for you:</p>
        <form method="POST" action="/poll/{poll_id}/respond">
            {times_html}
            <input type="email" name="email" placeholder="Your email" required
                   style="width: 100%; padding: 12px; margin: 16px 0; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; box-sizing: border-box;">
            <input type="text" name="name" placeholder="Your name" required
                   style="width: 100%; padding: 12px; margin: 0 0 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; box-sizing: border-box;">
            <textarea name="message" placeholder="Any notes? (optional)"
                      style="width: 100%; padding: 12px; margin: 0 0 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; min-height: 60px; box-sizing: border-box;"></textarea>
            <button type="submit"
                    style="width: 100%; padding: 14px; background: #007AFF; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;">
                Submit
            </button>
        </form>
    </body>
    </html>
    """)


@poll_router.post("/{poll_id}/respond")
async def submit_poll_response(poll_id: str, request: Request):
    """Handle a poll response submission."""
    form = await request.form()
    email = form.get("email", "")
    name = form.get("name", "")
    message = form.get("message", "")

    selected = [v for k, v in form.multi_items() if k == "times"]

    supabase.table("poll_responses").upsert({
        "poll_id": poll_id,
        "respondent_email": email,
        "respondent_name": name,
        "selected_times": [int(s) for s in selected],
        "message": message,
    }, on_conflict="poll_id,respondent_email").execute()

    poll_result = supabase.table("polls").select("*").eq("id", poll_id).execute()
    if not poll_result.data:
        return HTMLResponse("<h1>Poll not found</h1>", status_code=404)
    poll_data = poll_result.data[0]
    responses = supabase.table("poll_responses").select("*").eq("poll_id", poll_id).execute()

    total_participants = len(poll_data["participants"])
    total_responses = len(responses.data)

    if total_responses >= total_participants:
        from collections import Counter
        all_selections = []
        for r in responses.data:
            all_selections.extend(r["selected_times"])

        counter = Counter(all_selections)
        best_time_idx = counter.most_common(1)[0][0] if counter else 0
        best_time = poll_data["proposed_times"][best_time_idx]

        from app.services.linq import linq_client
        conv_result = supabase.table("conversations").select("linq_chat_id").eq("user_id", poll_data["user_id"]).execute()

        if conv_result.data and conv_result.data[0].get("linq_chat_id"):
            names = [r["respondent_name"] for r in responses.data]
            await linq_client.send_message(
                conv_result.data[0]["linq_chat_id"],
                f"📊 Everyone responded to your \"{poll_data['title']}\" poll!\n\n"
                f"Best time: {best_time['label']}\n"
                f"All {', '.join(names)} are available then.\n\n"
                f"Should I create the event and send invites?"
            )

    return HTMLResponse("""
    <html>
    <body style="font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh;">
        <div style="text-align: center;">
            <h1>✅</h1>
            <h2>Thanks! Your response has been recorded.</h2>
            <p style="color: #666;">You can close this tab.</p>
        </div>
    </body>
    </html>
    """)
