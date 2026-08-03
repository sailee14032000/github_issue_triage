from enum import Enum
import re


class IssueCategory(str, Enum):
    BUG = "bug"
    ENHANCEMENT = "enhancement"
    QUESTION = "question"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    OTHER = "other"


_LABEL_ORDER = [
    IssueCategory.SECURITY,
    IssueCategory.BUG,
    IssueCategory.DOCUMENTATION,
    IssueCategory.ENHANCEMENT,
    IssueCategory.QUESTION,
    IssueCategory.OTHER,
]


def map_to_issue_category(raw_text: str) -> IssueCategory:
    text = (raw_text or "").strip().lower()
    if not text:
        return IssueCategory.OTHER

    for label in _LABEL_ORDER:
        if text == label.value:
            return label

    # Fall back to searching the first category token mentioned in priority order.
    for label in _LABEL_ORDER:
        if re.search(rf"\\b{re.escape(label.value)}\\b", text):
            return label

    return IssueCategory.OTHER
