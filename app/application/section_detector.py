"""Section detection for parsed articles."""

from __future__ import annotations

import re
import uuid

from bs4 import BeautifulSoup, NavigableString, Tag

from app.domain.article import Article, Section


def _generate_astra_id() -> str:
    return f"astra-{uuid.uuid4().hex[:8]}"


def detect_sections(article: Article) -> Article:
    """Detect semantic sections within an Article.

    Populates the `sections` field of the Article by tagging DOM nodes
    with unique `data-astra-id` attributes and updating `raw_html`.
    """
    if not article.raw_html:
        return article

    soup = BeautifulSoup(article.raw_html, "html.parser")
    sections: list[Section] = []

    def _mark_and_create_section(
        element: Tag, name: str, sec_type: str, content_html: str
    ) -> None:
        astra_id = _generate_astra_id()
        element["data-astra-id"] = astra_id
        sections.append(
            Section(
                name=name,
                type=sec_type,
                astra_id=astra_id,
                content=content_html,
            )
        )

    # 1. Semantic Sections (based on headings)
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    # Introduction: Wrap everything before the first h2/h3 in a div if needed,
    # or just tag the first element. To be safe and preserve all nodes (including text),
    # we will wrap intro siblings in a <div class="astra-intro-wrapper">.
    first_major_heading = soup.find(["h2", "h3"])
    if first_major_heading:
        intro_siblings = []
        for sibling in first_major_heading.previous_siblings:
            if isinstance(sibling, Tag) and sibling.name in ["h1"]:
                continue
            intro_siblings.append(sibling)
        intro_siblings.reverse()
        
        if intro_siblings:
            wrapper = soup.new_tag("div")
            wrapper["class"] = "astra-wrapper"
            # Insert wrapper before the first sibling
            intro_siblings[0].insert_before(wrapper)
            for sib in intro_siblings:
                wrapper.append(sib)
            
            _mark_and_create_section(
                wrapper, "Introduction", "introduction", str(wrapper)
            )

    # For headings, we will wrap the heading and its content in a div to preserve all nodes
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
            # We want to wrap the heading and all siblings until the next heading of same/higher level
            content_nodes = [h]
            for sibling in h.next_siblings:
                if isinstance(sibling, Tag) and sibling.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    if int(sibling.name[1]) <= int(h.name[1]):
                        break
                content_nodes.append(sibling)
            
            wrapper = soup.new_tag("div")
            wrapper["class"] = "astra-wrapper"
            content_nodes[0].insert_before(wrapper)
            for node in content_nodes:
                wrapper.append(node)
                
            _mark_and_create_section(wrapper, sec_name, sec_type, str(wrapper))

    # 2. Date Section (look for <time> or regex in <p>)
    date_pattern = re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b",
        re.IGNORECASE,
    )
    for p in soup.find_all(["p", "time"]):
        if date_pattern.search(p.text):
            _mark_and_create_section(p, "Date Section", "date_section", str(p))

    # 3. Media (Images and Videos)
    for img in soup.find_all("img"):
        alt = str(img.get("alt", "Image"))
        _mark_and_create_section(img, f"Image: {alt}", "image", str(img))

    for vid in soup.find_all(["video", "iframe"]):
        src = str(vid.get("src", ""))
        if vid.name == "iframe" and "youtube" not in src.lower() and "vimeo" not in src.lower():
            continue
        _mark_and_create_section(vid, "Video", "video", str(vid))

    # 4. Links (External / Internal)
    for a in soup.find_all("a"):
        href = str(a.get("href", ""))
        if not href:
            continue
        is_external = href.startswith("http")
        link_type = "external_link" if is_external else "internal_link"
        name = "External Link" if is_external else "Internal Link"
        _mark_and_create_section(a, f"{name}: {a.text.strip()}", link_type, str(a))

    article.sections = sections
    # VERY IMPORTANT: update raw_html to include the injected data-astra-id attributes!
    article.raw_html = str(soup)
    return article
