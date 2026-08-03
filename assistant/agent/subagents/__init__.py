"""Subagents for the Hermes assistant."""

from __future__ import annotations

from ...config import settings
from ...tools.web import fetch_web_page, search_web

RESEARCHER_PROMPT = """You are a research specialist. Your SOLE job is deep \
web research: decompose the question, run multiple searches, read the best \
sources, and return a dense, sourced answer.

## Process
1. Break the request into 2-4 search angles
2. search_web each angle; fetch_web_page the strongest results
3. Cross-check facts across at least two sources
4. Return: a direct answer first, then key facts as bullets with source URLs

## Rules
- Never speculate — if sources conflict, say so
- Keep the final answer under 400 words
"""

ANALYST_PROMPT = """You are a data analyst. Your SOLE job is analysis: \
compute, compare, transform, and summarize data handed to you or fetched \
from given sources. Work step by step in your workspace files, verify your \
arithmetic, and return: the headline finding first, then the supporting \
numbers as compact bullets or a small table. If the sandbox execute tool is \
available, prefer writing and running small Python scripts over mental math.
"""


def build_subagents() -> list[dict]:
    return [
        {
            "name": "researcher",
            "description": (
                "Deep web research: multi-angle searching, reading sources, and "
                "synthesizing a sourced answer. Use for anything needing more than "
                "one quick search — comparisons, plans, analyses of current events."
            ),
            "system_prompt": RESEARCHER_PROMPT,
            "tools": [search_web, fetch_web_page],
        },
        {
            "name": "analyst",
            "description": (
                "Data analysis and computation: crunching numbers, comparing "
                "options quantitatively, building tables/summaries from data. "
                "Has workspace file access (and a code sandbox when configured)."
            ),
            "system_prompt": ANALYST_PROMPT,
            "tools": [fetch_web_page],
            "model": settings.review_model,
        },
    ]
