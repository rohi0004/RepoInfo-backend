"""System + starter prompts and a tiny Jinja2 renderer.

Keeps prompts declarative and versionable, so they can be seeded into
`prompt_templates` at boot and exposed via `/chat/prompt-templates`.
"""

from dataclasses import dataclass, field
from typing import Any

from jinja2 import Environment, StrictUndefined

_env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


@dataclass(slots=True)
class PromptSpec:
    key: str
    name: str
    icon: str
    description: str
    template: str
    variables: list[str] = field(default_factory=list)
    is_system: bool = True


SYSTEM_PROMPT = """You are RepoInfo, an AI-powered senior software engineer assisting the user in exploring, understanding, and improving a specific Git repository named {{ repository_full_name }}.

Guidelines:
- Ground every answer in the provided repository context. When you cite code, use fenced code blocks with the language, followed by a `<file_path>:<start_line>-<end_line>` reference on a new line.
- Prefer concise, high-signal explanations. Do not restate the prompt or produce filler.
- If information is missing, say so and suggest which file(s) would be most informative to inspect.
- Never invent file paths, function names, or APIs that were not in the context.
"""

CONTEXT_HEADER = """You have access to the following repository context.

Repository: {{ repository_full_name }}
Primary language: {{ primary_language | default('Unknown') }}
Active branch: {{ active_branch | default('main') }}

Relevant excerpts:

{% for chunk in chunks %}
--- {{ chunk.source_path }}{% if chunk.line_start %} (lines {{ chunk.line_start }}-{{ chunk.line_end }}){% endif %} ---
{{ chunk.content }}

{% endfor %}
"""

STARTERS: list[PromptSpec] = [
    PromptSpec(
        key="explain_repo",
        name="Explain this repository",
        icon="Sparkles",
        description="High-level walkthrough of the repository.",
        template=(
            "Give me a high-level walkthrough of this repository. Cover the overall "
            "architecture, key modules, how they interact, and any notable patterns."
        ),
    ),
    PromptSpec(
        key="onboarding_map",
        name="Onboarding map",
        icon="Map",
        description="File tour ordered by relevance for a new engineer.",
        template=(
            "I'm a new engineer joining this project. Suggest a reading order of the "
            "most important files with a 1-2 sentence blurb per file."
        ),
    ),
    PromptSpec(
        key="find_bugs",
        name="Find potential bugs",
        icon="Bug",
        description="Static-analysis-style walkthrough of risky code.",
        template=(
            "Perform a careful review of the repository looking for bugs, race conditions, "
            "and correctness issues. Cite file paths and line numbers."
        ),
    ),
    PromptSpec(
        key="security_audit",
        name="Security audit",
        icon="Shield",
        description="Application security review with severity ratings.",
        template=(
            "Perform a security-focused review of this repository. For each finding, "
            "give a severity, description, affected file/line, and remediation."
        ),
    ),
    PromptSpec(
        key="test_gaps",
        name="Test coverage gaps",
        icon="TestTube",
        description="Highlights uncovered flows and suggests tests.",
        template=(
            "Identify the most important code paths that are under-tested. "
            "Suggest concrete test cases (input, expected output) for each."
        ),
    ),
    PromptSpec(
        key="refactor_targets",
        name="Refactor targets",
        icon="Wrench",
        description="Top refactor candidates prioritised by impact.",
        template=(
            "Suggest the top refactor opportunities in this codebase, prioritised by "
            "impact vs effort. For each, describe the current state and the target state."
        ),
    ),
]

PROMPTS: dict[str, PromptSpec] = {p.key: p for p in STARTERS}


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    return _env.from_string(template).render(**variables)


def build_system_message(repository_full_name: str) -> str:
    return render_prompt(SYSTEM_PROMPT, {"repository_full_name": repository_full_name})


def build_context_message(
    *,
    repository_full_name: str,
    primary_language: str | None,
    active_branch: str | None,
    chunks: list[dict],
) -> str:
    return render_prompt(
        CONTEXT_HEADER,
        {
            "repository_full_name": repository_full_name,
            "primary_language": primary_language,
            "active_branch": active_branch,
            "chunks": chunks,
        },
    )
