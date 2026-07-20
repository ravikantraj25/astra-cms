"""Section detection for parsed articles."""

from __future__ import annotations

import re
import uuid

from bs4 import BeautifulSoup, Tag

from app.domain.article import Article, Section, SectionType

# Module-level constants
_ASTRA_ID_ATTR = "data-astra-id"
_ASTRA_WRAPPER_CLASS = "astra-wrapper"

_DATE_PATTERN = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b",
    re.IGNORECASE,
)

_HEADING_TAGS = ["h2", "h3", "h4", "h5", "h6"]

_HEADING_SECTIONS = [
    (("table of contents", "toc"), "Table of Contents", SectionType.TABLE_OF_CONTENTS),
    (("venue", "location"), "Venue", SectionType.VENUE),
    (("schedule", "agenda"), "Schedule", SectionType.SCHEDULE),
    (("faq", "frequently asked questions"), "FAQs", SectionType.FAQS),
    (("history",), "History", SectionType.HISTORY),
    (("conclusion",), "Conclusion", SectionType.CONCLUSION),
]


def _generate_astra_id() -> str:
    return f"astra-{uuid.uuid4().hex[:12]}"


def detect_sections(article: Article) -> Article:
    """Detect semantic sections within an Article.

    Populates the `sections` field of the Article by tagging DOM nodes
    with unique `data-astra-id` attributes and updating `raw_html`.
    """
    if not article.raw_html:
        return article.model_copy()

    soup = BeautifulSoup(article.raw_html, "html.parser")
    
    # Store references to marked tags so we can extract their final HTML
    # after all DOM manipulations (including nested modifications) are complete.
    section_placeholders: list[tuple[Tag, str, SectionType, str]] = []

    def _mark_section(
        element: Tag, name: str, sec_type: SectionType
    ) -> None:
        astra_id = _generate_astra_id()
        element[_ASTRA_ID_ATTR] = astra_id
        section_placeholders.append((element, name, sec_type, astra_id))

    def _is_already_wrapped(element: Tag) -> bool:
        """Check if element or any of its parents already have a data-astra-id."""
        if not isinstance(element, Tag):
            return False
            
        if element.get(_ASTRA_ID_ATTR):
            return True
            
        for parent in element.parents:
            if isinstance(parent, Tag) and parent.get(_ASTRA_ID_ATTR):
                return True
        return False

    def _get_heading_section_match(text: str) -> tuple[str, SectionType] | None:
        text = text.lower()
        for keywords, name, sec_type in _HEADING_SECTIONS:
            if any(kw in text for kw in keywords):
                return name, sec_type
        return None

    # 1. Semantic Sections (based on headings)
    headings = soup.find_all(_HEADING_TAGS)

    # Introduction: Wrap everything before the first h2/h3 in a div
    first_major_heading = soup.find(["h2", "h3"])
    if first_major_heading:
        intro_siblings = []
        for sibling in first_major_heading.previous_siblings:
            # Stop gathering if we hit an h1 (to avoid reordering content before h1)
            if isinstance(sibling, Tag) and sibling.name in ["h1"]:
                break
            intro_siblings.append(sibling)
            
        intro_siblings.reverse()
        
        if intro_siblings:
            wrapper = soup.new_tag("div")
            wrapper["class"] = _ASTRA_WRAPPER_CLASS
            
            # Insert wrapper before the first collected sibling
            intro_siblings[0].insert_before(wrapper)
            
            # Append moves the node safely into the wrapper
            for sib in intro_siblings:
                wrapper.append(sib)
            
            _mark_section(wrapper, "Introduction", SectionType.INTRODUCTION)

    # For headings, wrap the heading and its content in a div
    for h in headings:
        if _is_already_wrapped(h):
            continue
            
        text = h.get_text(" ", strip=True)
        match = _get_heading_section_match(text)
        
        if match:
            sec_name, sec_type = match
            
            # Wrap the heading and all siblings until the next heading of same/higher level
            content_nodes = [h]
            for sibling in h.next_siblings:
                if isinstance(sibling, Tag) and sibling.name in _HEADING_TAGS:
                    if int(sibling.name[1]) <= int(h.name[1]):
                        break
                content_nodes.append(sibling)
            
            wrapper = soup.new_tag("div")
            wrapper["class"] = _ASTRA_WRAPPER_CLASS
            
            content_nodes[0].insert_before(wrapper)
            for node in content_nodes:
                wrapper.append(node)
                
            _mark_section(wrapper, sec_name, sec_type)

    # 2. Date Section
    for p in soup.find_all(["p", "time"]):
        if _is_already_wrapped(p):
            continue
        text = p.get_text(" ", strip=True)
        if _DATE_PATTERN.search(text):
            _mark_section(p, "Date Section", SectionType.DATE_SECTION)

    # 3. Media (Images and Videos)
    for img in soup.find_all("img"):
        if _is_already_wrapped(img):
            continue
        alt = str(img.get("alt", "Image"))
        _mark_section(img, f"Image: {alt}", SectionType.IMAGE)

    for vid in soup.find_all(["video", "iframe"]):
        if _is_already_wrapped(vid):
            continue
        src = str(vid.get("src", ""))
        if vid.name == "iframe" and "youtube" not in src.lower() and "vimeo" not in src.lower():
            continue
        _mark_section(vid, "Video", SectionType.VIDEO)

    # 4. Links (External / Internal)
    for a in soup.find_all("a"):
        if _is_already_wrapped(a):
            continue
        href = str(a.get("href", ""))
        if not href:
            continue
        is_external = href.startswith("http")
        link_type = SectionType.EXTERNAL_LINK if is_external else SectionType.INTERNAL_LINK
        name = "External Link" if is_external else "Internal Link"
        text = a.get_text(" ", strip=True)
        _mark_section(a, f"{name}: {text}", link_type)

    # Now that ALL DOM modifications are complete, extract the final HTML for each section.
    sections = [
        Section(
            name=name,
            type=sec_type,
            astra_id=astra_id,
            content=str(element)
        )
        for element, name, sec_type, astra_id in section_placeholders
    ]

    return article.model_copy(
        update={
            "sections": sections,
            "raw_html": str(soup)
        }
    )
