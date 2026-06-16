# Plan: Add JobStreet Indonesia Scraper

## Ringkasan (Summary)

Add a new `jobstreet` scraper module targeting `id.jobstreet.com`. Extracts job data **only from search result pages** — no detail-page fetches. Uses slug-based URLs, camelCase `data-automation` selectors, and server-side `daterange` filtering for `hours_old` support.

---

## Goals

- [x] Scrape JobStreet Indonesia (`id.jobstreet.com`) jobs via HTML parsing
- [x] Extract data **only from search result cards** (no individual job detail pages)
- [x] Use anti-bot mitigations (TLS client, delay, realistic headers, proxy support)
- [x] Build slug-style URLs (`/id/software-engineer-jobs/in-Jakarta`)
- [x] Implement `hours_old` via server-side `daterange` filter
- [x] Normalize output into standard `JobPost` Pydantic models
- [x] Register alongside existing scrapers in `jobspy/__init__.py`
- [x] Update documentation (`DOCS.md`, `README.md`)
- [x] Provide verification script to test the scraper

---

## Critical Implementation Details

### 1. URL Format — Slug-Based (NOT Query Params)

JobStreet Indonesia **redirects** query-param URLs (`/id/jobs?keywords=...&where=...`) with a 301 to slug URLs. The scraper must construct the slug directly:

```
https://id.jobstreet.com/id/software-engineer-jobs/in-Jakarta
https://id.jobstreet.com/id/backend-developer-jobs/in-Indonesia
```

Implementation in `jobspy/jobstreet/__init__.py`:

```python
def _build_url(self) -> str:
    search_term = self.scraper_input.search_term or ""
    location = self.scraper_input.location or ""
    search_slug = "-".join(search_term.lower().split()) + "-jobs" if search_term else "jobs"
    location_slug = "in-" + "-".join(location.split()) if location else ""
    url = f"{self.base_url}/{search_slug}"
    if location_slug:
        url += f"/{location_slug}"
    return url
```

### 2. HTML Selectors — camelCase `data-automation`

After live HTML inspection, JobStreet uses **camelCase** (not kebab-case) `data-automation` attributes inside `<article>` tags:

| Field | data-automation value |
|-------|----------------------|
| Title | `jobTitle` |
| Company | `jobCompany` |
| Location | `jobLocation` or `jobCardLocation` |
| Salary | `jobSalary` |
| Description | `jobShortDescription` |
| Date Posted | `jobListingDate` |
| Job URL | `job-list-view-job-link` |

Example card structure:
```html
<article>
  <a data-automation="job-list-view-job-link" href="/id/job/92517349">...</a>
  <span data-automation="jobTitle">Software Engineer</span>
  <span data-automation="jobCompany">PT Example</span>
  <span data-automation="jobLocation">Jakarta Raya</span>
  <span data-automation="jobSalary">Rp 15.000.000 – Rp 20.000.000 per month</span>
  <span data-automation="jobShortDescription">Build scalable apps...</span>
  <span data-automation="jobListingDate">26 hari yang lalu•Segera ditutup</span>
</article>
```

### 3. `hours_old` Support — Server-Side `daterange` Filter

Unlike LinkedIn/Indeed which use API parameters, **JobStreet exposes a UI date filter** that maps to the query parameter `?daterange=X`:

| hours_old value | daterange param | Label (Indonesian) |
|-----------------|-----------------|-------------------|
| <= 24 | `1` | Hari Ini |
| <= 72 | `3` | 3 hari terakhir |
| <= 168 | `7` | 7 hari terakhir |
| <= 336 | `14` | 14 hari terakhir |
| > 336 | `30` | 30 hari terakhir |

Implementation in `_fetch_page()`:

```python
if self.scraper_input.hours_old:
    hours = self.scraper_input.hours_old
    if hours <= 24:
        params["daterange"] = 1
    elif hours <= 72:
        params["daterange"] = 3
    elif hours <= 168:
        params["daterange"] = 7
    elif hours <= 336:
        params["daterange"] = 14
    else:
        params["daterange"] = 30
```

**Note:** This is a server-side filter. Client-side post-filtering is not needed for JobStreet.

### 4. Date Parsing — Indonesian Relative Dates

`jobspy/jobstreet/util.py` handles multiple Indonesian formats:

```python
def parse_date_posted(text: str) -> date | None:
    if not text:
        return None
    # Strip suffixes like "•Segera ditutup"
    text_clean = text.split("•")[0].strip()
    text_lower = text_clean.lower()
    today = datetime.today().date()

    if "hari ini" in text_lower:
        return today
    if "hari" in text_lower or "day" in text_lower:
        try:
            days = int("".join(filter(str.isdigit, text_lower)))
            return today - timedelta(days=days)
        except ValueError:
            return None
    if "jam yang lalu" in text_lower or "hours ago" in text_lower:
        return today  # posted within last few hours = today
    if "menit yang lalu" in text_lower or "minutes ago" in text_lower:
        return today
    return None
```

Examples:
- `"Hari Ini"` -> today
- `"23 jam yang lalu"` -> today
- `"7 jam yang lalu"` -> today
- `"1 hari yang lalu"` -> yesterday
- `"26 hari yang lalu•Segera ditutup"` -> 26 days ago (suffix stripped)

---

## Complete Implementation

See actual source files in `jobspy/jobstreet/` directory for final working code.

Key files:
- `jobspy/jobstreet/__init__.py` — Scraper class with slug URL builder and hours_old mapping
- `jobspy/jobstreet/constant.py` — Chrome 130 headers
- `jobspy/jobstreet/util.py` — Date parser and location parser

---

## Anti-Bot Strategy Detail

| Layer | Risk | Mitigation |
|-------|------|------------|
| **TLS Fingerprinting** | Server detects non-browser TLS handshake | `is_tls=True` uses `tls_client` which mimics Chrome JA3 signature |
| **Rate Limiting** | Too many requests too fast | Randomized 3-5s delay between pages; max 20 pages |
| **User-Agent Detection** | Outdated or generic UA flagged | Up-to-date Chrome 130 on macOS with full header set |
| **Cookie Tracking** | Session patterns detected | `clear_cookies=True` resets cookies each request |
| **IP Reputation** | Repeated scraping from same IP | User passes `proxies` parameter; scraper rotates per request |
| **Retry Handling** | Intermittent 429/503 errors | `has_retry=True` with exponential backoff on 429/500-504 |

---

## Limitations and Risks

1. **HTML Fragility**: If JobStreet redesigns their search result page, card selectors (`data-automation` attributes) may break.

2. **Blocking**: JobStreet/SEEK may deploy Cloudflare challenge pages or CAPTCHA.

3. **Incomplete Data**: Only search card data (no detail pages).

4. **No Multi-Region**: Indonesia only (`id.jobstreet.com`).

5. **Date Filter Bucketing**: `hours_old` maps to discrete `daterange` buckets (1/3/7/14/30 days). A request for `hours_old=48` will return jobs from last 3 days. This is JobStreet's UI limitation.

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Region | Indonesia only | MVP scope |
| Extraction | Search cards only | Fast, consistent with Bayt pattern |
| Deep fetch | Not implemented | Not requested |
| HTTP client | TLS client (`is_tls=True`) | Anti-bot evasion for SEEK Group |
| Delay | 3-5s randomized | Human-like pacing |
| Max pages | 20 | Prevent excessive crawling |
| URL format | Slug-based | Query params get 301-redirected |
| Selectors | camelCase `data-automation` | Matches actual JobStreet HTML |
| `hours_old` | `?daterange` param | Server-side filter discovered in refine panel |

---

## How to Extend to Other JobStreet Regions

To add Singapore, Malaysia, or Philippines:

1. Create `jobspy/jobstreet/sg.py`, `my.py`, `ph.py` inheriting from `JobStreet`
2. Override `base_url`: `https://sg.jobstreet.com/sg`, `https://my.jobstreet.com/my`, etc.
3. Adjust `parse_date_posted()` for English/Chinese date strings if needed
4. Verify `data-automation` selectors are the same (SEEK Group shared design system)

---

## Test Results

### `hours_old=24` (Hari Ini)
- **11 jobs found**
- All dated `2026-06-16`

### `hours_old=168` (7 hari terakhir)
- **50 jobs found**
- Distribution:
  - 2026-06-16: 7 jobs
  - 2026-06-15: 14 jobs
  - 2026-06-14: 1 job
  - 2026-06-12: 4 jobs
  - 2026-06-11: 12 jobs
  - 2026-06-10: 12 jobs

---

*Plan updated: 2026-06-16*
