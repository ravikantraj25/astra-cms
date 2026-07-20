"""Debug script to analyze prompt leakage and structure issues in post 2717."""
from app.application.quality_validator import QualityValidator
from bs4 import BeautifulSoup, Comment

orig = open('output/post_2717.html', encoding='utf-8').read()
updated = open('output/post_2717_updated.html', encoding='utf-8').read()

# Check prompt leakage
banned = [
    'SECTION UPDATE', 'UPDATED HTML', 'Reason:', 'Explanation:',
    'Note:', 'Sure', 'Certainly', '```html', '```markdown', '```',
]
lower_upd = updated.lower()
print("=== PROMPT LEAKAGE ANALYSIS ===")
for phrase in banned:
    if phrase.lower() in lower_upd:
        idx = lower_upd.index(phrase.lower())
        start = max(0, idx - 100)
        end = min(len(updated), idx + len(phrase) + 100)
        print(f'LEAKED: "{phrase}" at position {idx}')
        print(f'  Context: ...{updated[start:end]}...')
        print()

# Check structure
print("\n=== STRUCTURE ANALYSIS ===")
orig_soup = BeautifulSoup(orig, 'html.parser')
upd_soup = BeautifulSoup(updated, 'html.parser')

o_h = len(orig_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))
u_h = len(upd_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))
print(f'Headings: orig={o_h}, updated={u_h}')

o_cls = set()
u_cls = set()
o_ids = set()
u_ids = set()
for tag in orig_soup.find_all(True):
    if tag.get('class'):
        v = tag['class']
        if isinstance(v, list):
            o_cls.update(v)
        else:
            o_cls.add(str(v))
    if tag.get('id'):
        v = tag['id']
        if isinstance(v, list):
            o_ids.update(v)
        else:
            o_ids.add(str(v))
for tag in upd_soup.find_all(True):
    if tag.get('class'):
        v = tag['class']
        if isinstance(v, list):
            u_cls.update(v)
        else:
            u_cls.add(str(v))
    if tag.get('id'):
        v = tag['id']
        if isinstance(v, list):
            u_ids.update(v)
        else:
            u_ids.add(str(v))

missing_cls = o_cls - u_cls
missing_ids = o_ids - u_ids
print(f'Missing classes ({len(missing_cls)}): {missing_cls}')
print(f'Missing IDs ({len(missing_ids)}): {missing_ids}')

o_g = sum(1 for c in orig_soup.find_all(string=lambda text: isinstance(text, Comment)) if 'wp:' in str(c))
u_g = sum(1 for c in upd_soup.find_all(string=lambda text: isinstance(text, Comment)) if 'wp:' in str(c))
print(f'Gutenberg comments: orig={o_g}, updated={u_g}')

# Also run full validation
print("\n=== FULL VALIDATION REPORT ===")
report = QualityValidator.validate(orig, updated)
print(f'html_valid: {report.html_valid}')
print(f'prompt_leakage: {report.prompt_leakage}')
print(f'dangerous_html: {report.dangerous_html}')
print(f'images_preserved: {report.images_preserved}')
print(f'links_preserved: {report.links_preserved}')
print(f'tables_preserved: {report.tables_preserved}')
print(f'structure_preserved: {report.structure_preserved}')
print(f'status: {report.status}')
