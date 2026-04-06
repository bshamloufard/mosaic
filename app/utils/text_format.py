import re


def markdown_to_imessage(text: str) -> dict:
    """
    Convert markdown-formatted text to plain text + iMessage text_decorations.

    Supports:
    - **bold** → bold decoration
    - *italic* or _italic_ → italic decoration
    - ~~strikethrough~~ → strikethrough decoration

    Returns {"value": plain_text, "text_decorations": [...]}
    """
    decorations = []
    result = text

    # Process bold first (**text**) before italic (*text*)
    patterns = [
        (r'\*\*(.+?)\*\*', 'bold'),
        (r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', 'italic'),
        (r'_(.+?)_', 'italic'),
        (r'~~(.+?)~~', 'strikethrough'),
    ]

    for pattern, style in patterns:
        offset = 0
        new_result = ""
        last_end = 0

        for match in re.finditer(pattern, result):
            # Add text before this match
            new_result += result[last_end:match.start()]

            # Calculate position in the output string
            start_pos = len(new_result)
            inner_text = match.group(1)
            end_pos = start_pos + len(inner_text)

            new_result += inner_text
            last_end = match.end()

            decorations.append({
                "range": [start_pos, end_pos],
                "style": style,
            })

        new_result += result[last_end:]
        result = new_result

    # Clean up any remaining markdown artifacts
    # Remove ### headers but keep the text
    result = re.sub(r'^#{1,6}\s+', '', result, flags=re.MULTILINE)

    # Remove bullet point markers and replace with cleaner format
    result = re.sub(r'^[-•]\s+', '• ', result, flags=re.MULTILINE)

    return {
        "value": result,
        "text_decorations": decorations if decorations else None,
    }


def build_text_part(text: str) -> dict:
    """Build a Linq message text part with iMessage decorations from markdown."""
    formatted = markdown_to_imessage(text)
    part = {"type": "text", "value": formatted["value"]}
    if formatted["text_decorations"]:
        part["text_decorations"] = formatted["text_decorations"]
    return part
