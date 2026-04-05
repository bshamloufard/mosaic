import anthropic
import json
import logging
from app.config import settings
from app.agent.tools import TOOL_DEFINITIONS
from app.agent.tool_executor import execute_tool
from app.agent.system_prompt import build_system_prompt
from app.db.messages import save_message, get_recent_messages, delete_old_messages
from app.db.conversations import get_or_create_conversation, update_summary
from app.db.pending_actions import get_pending_actions

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def run_agent(
    user_id: str,
    user_message: str,
    chat_id: str,
) -> str:
    """
    Run the agent loop for a single user message.
    Returns the final text response to send back via iMessage.
    """
    conversation = await get_or_create_conversation(user_id, chat_id)
    conversation_id = conversation["id"]

    recent_messages = await get_recent_messages(conversation_id, limit=10)
    summary = conversation.get("summary", "")

    await save_message(conversation_id, "user", user_message)

    pending = await get_pending_actions(conversation_id)

    messages = []

    if summary:
        messages.append({
            "role": "user",
            "content": f"[CONVERSATION SUMMARY FROM EARLIER]: {summary}"
        })
        messages.append({
            "role": "assistant",
            "content": "I remember our earlier conversation. How can I help?"
        })

    for msg in recent_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    system_prompt = await build_system_prompt(user_id, pending)

    max_iterations = 15
    final_response = ""

    for iteration in range(max_iterations):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20241022",
                max_tokens=4096,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return "Sorry, I'm having trouble thinking right now. Try again in a moment!"

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    final_response += block.text
            break

        elif response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Tool call [{iteration}]: {block.name}({json.dumps(block.input)[:200]})")
                    try:
                        result = await execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            user_id=user_id,
                            conversation_id=conversation_id,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                        })
                    except Exception as e:
                        logger.error(f"Tool execution error: {block.name}: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": str(e)}),
                            "is_error": True,
                        })

            messages.append({"role": "user", "content": tool_results})

        else:
            logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
            break

    if not final_response:
        final_response = "I processed your request but something went wrong generating a response. Could you try again?"

    await save_message(conversation_id, "assistant", final_response)

    message_count = len(recent_messages)
    if message_count >= 10:
        await summarize_and_trim(conversation_id)

    return final_response


async def summarize_and_trim(conversation_id: str):
    """Summarize the oldest messages in the conversation and delete them."""
    all_messages = await get_recent_messages(conversation_id, limit=30)

    if len(all_messages) <= 10:
        return

    old_messages = all_messages[:-10]
    old_text = "\n".join([f"{m['role']}: {m['content']}" for m in old_messages])

    summary_response = client.messages.create(
        model="claude-haiku-4-5-20241022",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Summarize this conversation history concisely, preserving key decisions, scheduled events, and user preferences:\n\n{old_text}"
        }],
    )

    summary = summary_response.content[0].text
    await update_summary(conversation_id, summary)

    await delete_old_messages(conversation_id, keep_recent=10)
