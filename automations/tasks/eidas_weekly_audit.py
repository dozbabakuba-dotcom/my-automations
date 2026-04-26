from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from automations.core import automation


DEFAULT_URL = "https://eidas.tools"
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_REPORT_DIR = "reports/eidas-tools"

SOURCE_SHORTLIST = [
    "https://eur-lex.europa.eu/",
    "https://digital-strategy.ec.europa.eu/en/policies/eidas-regulation",
    "https://www.enisa.europa.eu/topics/cybersecurity-policy/eidas",
    "https://eulaw.ai/",
    "https://omnilaw.ai/",
    "https://www.lexlens.io/",
    "https://eidas-pro.com/",
    "https://www.eudi-wallet.eu/",
]


@dataclass(frozen=True)
class SiteSnapshot:
    url: str
    title: str
    text: str
    capture_method: str


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "eidas-weekly-audit/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    title = title_match.group(1).strip() if title_match else ""
    without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", without_scripts)
    text = re.sub(r"\s+", " ", text).strip()
    return f"{title}\n\n{text}".strip()


def _capture_with_playwright(url: str) -> SiteSnapshot | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as playwright:
            print("Nacitam eidas.tools v prohlizeci...", flush=True)
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            page.goto(url, wait_until="networkidle", timeout=45_000)

            password = os.getenv("EIDAS_AUDIT_PASSWORD", "").strip()
            password_fields = page.locator("input[type='password']")
            if password_fields.count() > 0:
                if not password:
                    browser.close()
                    raise SystemExit(
                        "eidas.tools zobrazuje password obrazovku. Pridej do .env "
                        "EIDAS_AUDIT_PASSWORD=... a spust audit znovu."
                    )
                password_fields.first.fill(password)
                page.keyboard.press("Enter")
                page.wait_for_load_state("networkidle", timeout=45_000)

            title = page.title()
            text = page.locator("body").inner_text(timeout=10_000)
            browser.close()
            print("Stranka nactena.", flush=True)
            return SiteSnapshot(url=url, title=title, text=text, capture_method="playwright")
    except Exception:
        return None


def _capture_site(url: str) -> SiteSnapshot:
    rendered = _capture_with_playwright(url)
    if rendered and rendered.text.strip():
        return rendered

    print("Pouzivam HTML fallback pro nacteni stranky...", flush=True)
    html = _fetch_html(url)
    text = _html_to_text(html)
    title = text.splitlines()[0] if text else url
    return SiteSnapshot(url=url, title=title, text=text, capture_method="html-fallback")


def _compact_text(value: str, limit: int = 18_000) -> str:
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "\n\n[Truncated for audit prompt]"


def _build_prompt(snapshot: SiteSnapshot) -> str:
    sources = "\n".join(f"- {source}" for source in SOURCE_SHORTLIST)
    site_text = _compact_text(snapshot.text)

    return textwrap.dedent(
        f"""
        You are a senior product strategist for legal systems, EU law research,
        eIDAS/EUDI workflows, legal operations productivity, and AI-assisted
        legal research tools.

        Produce a JSON object only. The JSON must match this shape:
        {{
          "executive_summary": "string",
          "recommendations": [
            {{
              "title": "string",
              "priority": "P0|P1|P2",
              "impact": "string",
              "why_now": "string",
              "suggested_change": "string",
              "inspiration": "string",
              "effort": "S|M|L"
            }}
          ],
          "do_not_do_yet": ["string"],
          "sources": [
            {{
              "title": "string",
              "url": "string",
              "why_it_matters": "string"
            }}
          ]
        }}

        Requirements:
        - Focus on eidas.tools as a practical productivity tool for lawyers and legal ops.
        - Compare it with EUR-Lex replacement attempts, AI legal research tools,
          legal workflow products, and eIDAS/EUDI compliance products.
        - Use web search for fresh context and cite useful sources.
        - Give 5 to 10 first-class recommendations.
        - Be concrete enough that a product builder can decide what to implement.
        - Do not recommend generic SEO fluff unless it directly improves adoption
          by lawyers or legal ops users.
        - Keep the recommendations strategic, not code-level.

        Curated source shortlist to consider:
        {sources}

        Captured website:
        URL: {snapshot.url}
        Title: {snapshot.title}
        Capture method: {snapshot.capture_method}

        Website text:
        {site_text}
        """
    ).strip()


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _generate_audit(snapshot: SiteSnapshot) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY neni nastaveny. Pridej ho do .env pro lokalni beh "
            "nebo jako GitHub Actions secret."
        )

    from openai import OpenAI

    print("Posilam podklady do OpenAI. Tohle muze trvat 1-3 minuty...", flush=True)
    client = OpenAI(api_key=api_key)
    model = os.getenv("EIDAS_AUDIT_MODEL", DEFAULT_MODEL)
    response = client.responses.create(
        model=model,
        tools=[{"type": "web_search"}],
        tool_choice="auto",
        input=[
            {
                "role": "system",
                "content": (
                    "You produce precise, source-aware legaltech product audit reports. "
                    "Return valid JSON only."
                ),
            },
            {"role": "user", "content": _build_prompt(snapshot)},
        ],
    )
    print("OpenAI vratilo odpoved, skladam report...", flush=True)
    return _extract_json(response.output_text)


def _clean_list(items: Any) -> list[Any]:
    return items if isinstance(items, list) else []


def _render_report(snapshot: SiteSnapshot, audit: dict[str, Any], report_date: date) -> str:
    lines = [
        f"# eidas.tools weekly audit - {report_date.isoformat()}",
        "",
        f"- Website: {snapshot.url}",
        f"- Capture method: {snapshot.capture_method}",
        f"- Model: {os.getenv('EIDAS_AUDIT_MODEL', DEFAULT_MODEL)}",
        "",
        "## Executive summary",
        "",
        str(audit.get("executive_summary", "")).strip() or "No summary returned.",
        "",
        "## Priority recommendations",
        "",
    ]

    recommendations = _clean_list(audit.get("recommendations"))
    if not recommendations:
        lines.append("No recommendations returned.")
    for index, item in enumerate(recommendations, start=1):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### {index}. {item.get('title', 'Untitled recommendation')}",
                "",
                f"- Priority: {item.get('priority', 'P1')}",
                f"- Effort: {item.get('effort', 'M')}",
                f"- Impact: {item.get('impact', '')}",
                f"- Why now: {item.get('why_now', '')}",
                f"- Suggested change: {item.get('suggested_change', '')}",
                f"- Inspiration: {item.get('inspiration', '')}",
                "",
            ]
        )

    lines.extend(["## Do not do yet", ""])
    do_not_do = _clean_list(audit.get("do_not_do_yet"))
    if do_not_do:
        for item in do_not_do:
            lines.append(f"- {item}")
    else:
        lines.append("- No deferred ideas returned.")

    lines.extend(["", "## Sources", ""])
    sources = _clean_list(audit.get("sources"))
    if sources:
        for source in sources:
            if isinstance(source, dict):
                title = source.get("title") or source.get("url") or "Source"
                url = source.get("url", "")
                why = source.get("why_it_matters", "")
                lines.append(f"- [{title}]({url}) - {why}" if url else f"- {title} - {why}")
    else:
        lines.append("- No sources returned.")

    lines.append("")
    return "\n".join(lines)


def _write_report(markdown: str, report_dir: str, report_date: date) -> Path:
    directory = Path(report_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{report_date.isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


@automation(
    "eidas-weekly-audit",
    description="Vytvori AI report s doporucenimi pro zlepseni eidas.tools",
)
def run() -> None:
    url = os.getenv("EIDAS_AUDIT_URL", DEFAULT_URL)
    report_dir = os.getenv("EIDAS_AUDIT_REPORT_DIR", DEFAULT_REPORT_DIR)
    report_date = date.today()

    print("Startuji eidas.tools weekly audit...", flush=True)
    snapshot = _capture_site(url)
    audit = _generate_audit(snapshot)
    markdown = _render_report(snapshot, audit, report_date)
    path = _write_report(markdown, report_dir, report_date)
    print(f"Report vytvoren: {path}")
