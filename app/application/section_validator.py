"""Validation feedback loop for AI-generated section updates."""

from __future__ import annotations

import collections
import re
from typing import List

from bs4 import BeautifulSoup

from app.domain.plan import SectionDecision
from app.domain.section_validation import SectionValidationResult

# Regex to find 4-digit years (e.g. 2024)
_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

# Regex to find full month names
_MONTHS = ["January", "February", "March", "April", "May", "June", 
           "July", "August", "September", "October", "November", "December"]
_MONTH_PATTERN = re.compile(r"\b(" + "|".join(_MONTHS) + r")\b", flags=re.IGNORECASE)

_DANGEROUS_TAGS = {"script", "object", "embed", "applet"}


class SectionValidator:
    """Validates an AI-generated section against strict rules to provide feedback."""

    @classmethod
    def validate(
        cls, original_html: str, updated_html: str, decision: SectionDecision
    ) -> SectionValidationResult:
        """Run all validation rules for a single section."""
        result = SectionValidationResult(is_valid=True)
        
        orig_soup = BeautifulSoup(original_html, "html.parser")
        upd_soup = BeautifulSoup(updated_html, "html.parser")
        
        orig_text = orig_soup.get_text()
        upd_text = upd_soup.get_text()

        cls._validate_html(upd_soup, updated_html, result)
        
        # If HTML is completely invalid or empty, stop checking other rules
        if not result.is_valid and any("HTML" in r for r in result.failed_rules):
            return result
            
        cls._validate_years(orig_text, upd_text, decision, result)
        cls._validate_dates(orig_text, upd_text, decision, result)
        cls._validate_links(orig_soup, upd_soup, result)
        cls._validate_images(orig_soup, upd_soup, result)
        cls._validate_headings(orig_soup, upd_soup, result)
        cls._validate_schema(orig_soup, upd_soup, result)
        cls._validate_required_updates(upd_text, decision, result)

        return result

    @classmethod
    def _validate_html(
        cls, upd_soup: BeautifulSoup, updated_html: str, result: SectionValidationResult
    ) -> None:
        """RULE: Output must be valid HTML with no dangerous tags."""
        if not updated_html.strip():
            result.add_failure("Generated HTML is empty.")
            return

        if not upd_soup.find(True) and "<" in updated_html and ">" in updated_html:
             # Basic check if it's completely malformed
             pass
             
        for tag in upd_soup.find_all(True):
            if tag.name in _DANGEROUS_TAGS:
                result.add_failure(f"Dangerous tag <{tag.name}> detected. Do not inject scripts.")
            elif tag.name == "iframe":
                src_val = tag.get("src", "")
                src = "".join(src_val).lower() if isinstance(src_val, list) else str(src_val).lower()
                if "youtube" not in src and "vimeo" not in src:
                    result.add_failure("Untrusted iframe detected. Only YouTube and Vimeo are allowed.")

            for attr, val in tag.attrs.items():
                attr_lower = attr.lower()
                if attr_lower.startswith("on"):
                    result.add_failure(f"Dangerous event handler '{attr}' detected.")
                elif attr_lower in ("href", "src"):
                    val_str = "".join(val).lower() if isinstance(val, list) else str(val).lower()
                    if val_str.startswith("javascript:") or val_str.startswith("vbscript:"):
                        result.add_failure(f"Dangerous javascript/vbscript protocol in '{attr}'.")

    @classmethod
    def _validate_years(
        cls, orig_text: str, upd_text: str, decision: SectionDecision, result: SectionValidationResult
    ) -> None:
        """RULE: Never invent dates. Any newly introduced year must be in required_entities."""
        orig_years = set(match.group(1) for match in _YEAR_PATTERN.finditer(orig_text))
        upd_years = set(match.group(1) for match in _YEAR_PATTERN.finditer(upd_text))
        
        new_years = upd_years - orig_years
        allowed_years = {str(req) for req in decision.required_entities}
        
        for year in new_years:
            if year not in allowed_years:
                result.add_failure(f"Year {year} was hallucinated. You must only use years provided in REQUIRED ENTITIES.")

    @classmethod
    def _validate_dates(
        cls, orig_text: str, upd_text: str, decision: SectionDecision, result: SectionValidationResult
    ) -> None:
        """RULE: Never invent dates. Any newly introduced month must be in required_entities."""
        orig_months = set(match.group(1).lower() for match in _MONTH_PATTERN.finditer(orig_text))
        upd_months = set(match.group(1).lower() for match in _MONTH_PATTERN.finditer(upd_text))
        
        new_months = upd_months - orig_months
        allowed_entities_lower = {str(req).lower() for req in decision.required_entities}
        
        for month in new_months:
            if month not in allowed_entities_lower and not any(month in allowed for allowed in allowed_entities_lower):
                result.add_failure(f"Month '{month.title()}' was hallucinated. Do not invent dates.")

    @classmethod
    def _validate_links(
        cls, orig_soup: BeautifulSoup, upd_soup: BeautifulSoup, result: SectionValidationResult
    ) -> None:
        """RULE: The exact set of links (<a> tags) must be preserved."""
        def get_hrefs(soup: BeautifulSoup) -> list[str]:
            return [str(a.get("href", "")).strip() for a in soup.find_all("a")]
            
        orig_links = collections.Counter(get_hrefs(orig_soup))
        upd_links = collections.Counter(get_hrefs(upd_soup))
        
        for link, count in orig_links.items():
            if upd_links[link] < count:
                result.add_failure(f"Link href='{link}' was removed or modified. You must preserve all links exactly.")

    @classmethod
    def _validate_images(
        cls, orig_soup: BeautifulSoup, upd_soup: BeautifulSoup, result: SectionValidationResult
    ) -> None:
        """RULE: The exact set of image sources (<img> tags) must be preserved."""
        def get_srcs(soup: BeautifulSoup) -> list[str]:
            return [str(img.get("src", "")).strip() for img in soup.find_all("img")]
            
        orig_srcs = collections.Counter(get_srcs(orig_soup))
        upd_srcs = collections.Counter(get_srcs(upd_soup))
        
        for src, count in orig_srcs.items():
            if upd_srcs[src] < count:
                result.add_failure(f"Image src='{src}' was removed or modified. You must preserve all images exactly.")

    @classmethod
    def _validate_headings(
        cls, orig_soup: BeautifulSoup, upd_soup: BeautifulSoup, result: SectionValidationResult
    ) -> None:
        """RULE: Exact count and tag levels of headings must be preserved."""
        def get_headings(soup: BeautifulSoup) -> list[str]:
            return [tag.name for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
            
        orig_h = get_headings(orig_soup)
        upd_h = get_headings(upd_soup)
        
        if collections.Counter(orig_h) != collections.Counter(upd_h):
            result.add_failure(f"Heading structure was modified. Expected {collections.Counter(orig_h)}, got {collections.Counter(upd_h)}. Do not change heading tags.")

    @classmethod
    def _validate_schema(
        cls, orig_soup: BeautifulSoup, upd_soup: BeautifulSoup, result: SectionValidationResult
    ) -> None:
        """RULE: Classes, IDs, and schema.org attributes must be preserved."""
        def get_schema_attrs(soup: BeautifulSoup) -> set[tuple[str, str]]:
            attrs = set()
            for tag in soup.find_all(True):
                for attr_name in ["id", "class", "itemscope", "itemtype", "itemprop"]:
                    val = tag.get(attr_name)
                    if val is None:
                        continue
                    if isinstance(val, list):
                        for v in val:
                            attrs.add((attr_name, str(v)))
                    else:
                        attrs.add((attr_name, str(val)))
            return attrs
            
        orig_attrs = get_schema_attrs(orig_soup)
        upd_attrs = get_schema_attrs(upd_soup)
        
        missing = orig_attrs - upd_attrs
        if missing:
            for attr_name, attr_val in missing:
                result.add_failure(f"Schema attribute {attr_name}='{attr_val}' was removed. You must preserve schema exactly.")

    @classmethod
    def _validate_required_updates(
        cls, upd_text: str, decision: SectionDecision, result: SectionValidationResult
    ) -> None:
        """RULE: All REQUIRED ENTITIES must be present in the output."""
        upd_text_lower = upd_text.lower()
        for entity in decision.required_entities:
            if entity.lower() not in upd_text_lower:
                result.add_failure(f"Required entity '{entity}' is missing from the generated HTML.")
