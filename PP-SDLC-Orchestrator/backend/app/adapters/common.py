"""Small helpers shared between mock and LLM-backed adapters for the same
agent — keeps the two runtimes from duplicating template-manipulation code
when only the source of the content (canned pool vs real model) differs.
"""


def version_label(run_number: int) -> str:
    return "v0.1" if run_number == 1 else f"v0.{run_number}"
