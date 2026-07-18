"""Section detection for parsed articles."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from app.domain.article import Article, Section


def detect_sections(article: Article) -> Article:
    """Detect semantic sections within an Article.

    Populates the `sections` field of the Article based on rule-based heuristics.
    """
    if not article.raw_html:
        return article

    soup = BeautifulSoup(article.raw_html, "html.parser")
    sections: list[Section] = []

    # Track the current search position in raw_html to find accurate offsets
    search_pos = 0

    def find_position(text_snippet: str, start_search: int = 0) -> int:
        """Find the character index of a text snippet in the raw HTML."""
        if not text_snippet:
            return -1
        # Try to find the exact text in the raw HTML
        idx = article.raw_html.find(text_snippet, start_search)
        if idx != -1:
            return idx
        return -1

    # 1. Semantic Sections (based on headings)
    # We will iterate through all top-level elements or just headings to find sections
    # A section is defined by a heading and all its following siblings
    # until the next heading of same or higher level.
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    # Introduction: Everything before the first h2/h3
    first_major_heading = soup.find(["h2", "h3"])
    if first_major_heading:
        intro_content = []
        for sibling in first_major_heading.previous_siblings:
            if isinstance(sibling, Tag) and sibling.name not in ["h1"]:
                intro_content.append(str(sibling))
        intro_content.reverse()
        intro_html = "".join(intro_content).strip()
        if intro_html:
            start_idx = 0
            end_idx = find_position(first_major_heading.text)
            if end_idx == -1:
                end_idx = len(intro_html)
            sections.append(
                Section(
                    name="Introduction",
                    type="introduction",
                    start_position=start_idx,
                    end_position=end_idx,
                    content=intro_html,
                )
            )

    # Helper to extract content until next heading
    def extract_section_content(heading: Tag) -> str:
        content = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                # Stop if it's a heading of same or higher level
                if int(sibling.name[1]) <= int(heading.name[1]):
                    break
            if isinstance(sibling, Tag):
                content.append(str(sibling))
        return "".join(content).strip()

    for h in headings:
        text = h.text.lower()
        sec_name = None
        sec_type = None

        if "table of contents" in text or "toc" == text:
            sec_name = "Table of Contents"
            sec_type = "table_of_contents"
        elif "venue" in text or "location" in text:
            sec_name = "Venue"
            sec_type = "venue"
        elif "schedule" in text or "agenda" in text:
            sec_name = "Schedule"
            sec_type = "schedule"
        elif "faq" in text or "frequently asked questions" in text:
            sec_name = "FAQs"
            sec_type = "faqs"
        elif "history" in text:
            sec_name = "History"
            sec_type = "history"
        elif "conclusion" in text:
            sec_name = "Conclusion"
            sec_type = "conclusion"

        if sec_name and sec_type:
            content = extract_section_content(h)
            start_idx = find_position(h.text, search_pos)
            if start_idx != -1:
                search_pos = start_idx
            else:
                start_idx = 0

            end_idx = start_idx + len(content) + len(h.text)

            sections.append(
                Section(
                    name=sec_name,
                    type=sec_type,
                    start_position=start_idx,
                    end_position=end_idx,
                    content=content,
                )
            )

    # 2. Date Section
    # Look for <time> tags or paragraphs with
    # date patterns
    date_pattern = re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]* \d{1,2},? \d{4}\b",
        re.IGNORECASE,
    )
    for p in soup.find_all(["p", "time"]):
        if date_pattern.search(p.text):
            start_idx = find_position(p.text)
            sections.append(
                Section(
                    name="Date Section",
                    type="date_section",
                    start_position=max(0, start_idx),
                    end_position=max(0, start_idx) + len(p.text),
                    content=str(p),
                )
            )

    # 3. Media (Images and Videos)
    for img in soup.find_all("img"):
        src = str(img.get("src", ""))
        alt = str(img.get("alt", "Image"))
        start_idx = find_position(src)
        sections.append(
            Section(
                name=f"Image: {alt}",
                type="image",
                start_position=max(0, start_idx),
                end_position=max(0, start_idx) + len(str(img)),
                content=str(img),
            )
        )

    for vid in soup.find_all(["video", "iframe"]):
        src = str(vid.get("src", ""))
        if (
            vid.name == "iframe"
            and "youtube" not in src.lower()
            and "vimeo" not in src.lower()
        ):
            continue
        start_idx = find_position(src)
        sections.append(
            Section(
                name="Video",
                type="video",
                start_position=max(0, start_idx),
                end_position=max(0, start_idx) + len(str(vid)),
                content=str(vid),
            )
        )

    # 4. Links (External / Internal)
    for a in soup.find_all("a"):
        href = str(a.get("href", ""))
        if not href:
            continue

        is_external = href.startswith("http")
        link_type = "external_link" if is_external else "internal_link"
        name = "External Link" if is_external else "Internal Link"

        start_idx = find_position(a.text)
        sections.append(
            Section(
                name=f"{name}: {a.text.strip()}",
                type=link_type,
                start_position=max(0, start_idx),
                end_position=max(0, start_idx) + len(str(a)),
                content=str(a),
            )
        )

    article.sections = sections
    return article
