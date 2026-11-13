"""Conservative email-body detection for calendar description previews."""
import re

GREETING = re.compile(r"(?im)^[ \t]*(?:(?:hi|hello|dear)\s+[A-Za-z][^\n]{0,65}[,!]|(?:team|all),)[ \t]*$")
CLOSING = re.compile(r"(?im)^[ \t]*(?:thank\s+you[!.,]?|thanks[!.,]?|(?:kind\s+|best\s+)?regards[,]?|best\s+wishes[,]?)\s*$")
INVITATION = re.compile(
    r"(?is)\b(?:please\s+join\s+(?:the\s+)?meeting|monthly\s+check[- ]in|"
    r"inviting\s+you\s+to\s+a\s+scheduled\s+zoom\s+meeting|"
    r"unable\s+to\s+join|join\s+(?:us\s+for|the)\s+(?:a\s+)?(?:meeting|call))\b"
)
HEADER = re.compile(r"(?im)^[ \t]*(From|Sent|Date|To|Cc|Subject):[^\n]+$")
REPLY = re.compile(r"(?im)^[ \t]*(?:[-_]{2,}\s*(?:Original Message|Forwarded message)\s*[-_]{2,}|On [^\n]{3,180} wrote:)\s*$")
NOTES = re.compile(r"(?im)^[ \t]*(?:Meeting\s+(?:notes|details)|Work\s+performed)\s*:[ \t]*")


def strip_email_description(text: str) -> str:
    """Keep independent notes, but omit identified invitation bodies/threads.

    A greeting alone, signature alone, or an address is not sufficient evidence.
    Generic email prose requires a greeting+closing; invitation language can
    substitute for the closing. Header-based detection requires a From header
    and at least two other mail headers in the same compact block.
    """
    starts = []
    for greeting in GREETING.finditer(text):
        tail = text[greeting.end():]
        if CLOSING.search(tail) or INVITATION.search(tail):
            starts.append(greeting.start())
    headers = list(HEADER.finditer(text))
    for header in headers:
        if header.group(1).lower() != 'from':
            continue
        nearby = [h for h in headers if header.start() <= h.start() < header.start() + 650]
        if len({h.group(1).lower() for h in nearby}) >= 3:
            starts.append(header.start())
    starts.extend(m.start() for m in REPLY.finditer(text))
    if not starts:
        return text
    start = min(starts)
    prefix = text[:start].strip()
    tail = text[start:]
    preserved = []
    # Explicit work notes following an email body are independent, editable
    # content. Stop at the next mail/signature marker rather than copying it.
    for note in NOTES.finditer(tail):
        end = len(tail)
        for pattern in (GREETING, CLOSING, HEADER, REPLY):
            boundary = pattern.search(tail, note.end())
            if boundary:
                end = min(end, boundary.start())
        block = tail[note.start():end].strip()
        block = re.split(r"(?im)^\s*[─━_—-]{4,}\s*$", block, maxsplit=1)[0].strip()
        if block:
            preserved.append(block)
    return '\n\n'.join(part for part in [prefix, *preserved] if part)
