def build_triage_prompt(title: str, body: str) -> str:
    safe_title = title or ""
    safe_body = body or ""
    return f"""You are classifying GitHub issues from a software repository into exactly one category. Read the issue title and body, then respond with a single category label.

CATEGORIES (choose exactly one):

bug
An existing feature or command is not working as intended. The issue reports a defect, error, crash, incorrect output, or unexpected behavior in something that already exists. Includes: error messages, stack traces, incorrect results, flags being ignored, inconsistent behavior between similar commands, broken releases or builds.

enhancement
A request for new capability that does not currently exist. The issue asks for a new feature, flag, command, output format, or platform support. This includes requests where the underlying subject matter is documentation-related (e.g. "add man page export," "add extension for X") - if the ask is for new tooling or capability, it is enhancement, not documentation.

question
The issue is seeking information, clarification, or guidance - not reporting a problem or requesting a feature. The reporter does not know something and is asking. Look for direct questions ("how do I...", "is it possible to...", "does X support..."), not just a question mark used rhetorically. Classify based on what the reporter is asking for as filed, not on what the eventual resolution might turn out to be.

documentation
The issue reports a problem with existing documentation content - inaccurate, missing, unclear, or broken (e.g. broken links, wrong examples, outdated instructions). Does NOT apply to requests for new documentation formats or tooling (those are enhancement).

security
The issue reports a security vulnerability, CVE, or a security-relevant defect (e.g. credential handling, unsafe permissions, dependency vulnerabilities).

other
The issue does not genuinely fit any of the above. Includes: spam, test/placeholder content, duplicate reports, or requests that are off-topic for this repository (e.g. proposals for an unrelated separate product), even if the reporter frames it using feature-request language.

RULES
1. Choose exactly one category. Never return more than one label, and never return free text outside the category name.
2. Base your classification only on the issue title and body provided below. Do not assume access to comments, labels, or resolution history.
3. Ignore tone, formatting quality, or sarcasm. A calmly written report and an informally written report should be classified the same way if their underlying content is the same.
4. If an issue could plausibly fit two categories, prioritize in this order: security > bug > documentation > enhancement > question > other.
5. Respond with only the category name, exactly as spelled above (lowercase, no punctuation, no explanation).

ISSUE TITLE:
{safe_title}

ISSUE BODY:
{safe_body}

CATEGORY:"""
