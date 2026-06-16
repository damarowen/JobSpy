from __future__ import annotations

import random
import time
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from jobspy.exception import JobStreetException
from jobspy.jobstreet.constant import headers as jobstreet_headers
from jobspy.jobstreet.util import parse_date_posted, parse_location
from jobspy.model import (
    Compensation,
    CompensationInterval,
    JobPost,
    JobResponse,
    Location,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.util import (
    create_logger,
    create_session,
    extract_salary,
    markdown_converter,
)

log = create_logger("JobStreet")


class JobStreet(Scraper):
    """JobStreet Indonesia scraper. Extracts job data from search result pages only."""

    base_url = "https://id.jobstreet.com/id"
    jobs_per_page = 20
    delay = 3
    band_delay = 2
    max_pages = 20

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        """Initialize with TLS client for anti-bot fingerprint evasion."""
        super().__init__(Site.JOBSTREET, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=True,  # TLS client mimics real browser
            has_retry=True,
            delay=5,
            clear_cookies=True,
        )
        self.session.headers.update(jobstreet_headers)
        if user_agent:
            self.session.headers["user-agent"] = user_agent
        self.scraper_input = None

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """Scrape JobStreet Indonesia search results."""
        self.scraper_input = scraper_input
        job_list: list[JobPost] = []
        seen_ids = set()
        page = 1

        while (
            len(job_list) < scraper_input.results_wanted + scraper_input.offset
            and page <= self.max_pages
        ):
            log.info(f"Fetching JobStreet page {page} / {self.max_pages}")
            try:
                jobs_on_page = self._fetch_page(page)
                if not jobs_on_page:
                    log.info(f"No jobs found on page {page}. Stopping.")
                    break

                initial_count = len(job_list)
                for job in jobs_on_page:
                    if job.id and job.id in seen_ids:
                        continue
                    if job.id:
                        seen_ids.add(job.id)
                    job_list.append(job)
                    if len(job_list) >= scraper_input.results_wanted + scraper_input.offset:
                        break

                if len(job_list) == initial_count:
                    log.info(f"No new jobs on page {page}. Stopping.")
                    break

            except Exception as e:
                log.error(f"Error fetching page {page}: {e}")
                break

            page += 1
            if len(job_list) < scraper_input.results_wanted + scraper_input.offset:
                sleep_time = random.uniform(self.delay, self.delay + self.band_delay)
                log.debug(f"Sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)

        return JobResponse(
            jobs=job_list[
                scraper_input.offset : scraper_input.offset + scraper_input.results_wanted
            ]
        )

    def _build_url(self) -> str:
        """Build JobStreet search URL using slug format."""
        search_term = self.scraper_input.search_term or ""
        location = self.scraper_input.location or ""
        
        # Build URL path segments
        search_slug = "-".join(search_term.lower().split()) + "-jobs" if search_term else "jobs"
        location_slug = "in-" + "-".join(location.split()) if location else ""
        
        url = f"{self.base_url}/{search_slug}"
        if location_slug:
            url += f"/{location_slug}"
        return url

    def _fetch_page(self, page: int) -> list[JobPost]:
        """Fetch and parse one search result page."""
        url = self._build_url()
        params = {}
        if page > 1:
            params["page"] = page

        # Map hours_old to JobStreet daterange filter
        if self.scraper_input.hours_old:
            hours = self.scraper_input.hours_old
            if hours <= 24:
                params["daterange"] = 1      # Hari Ini
            elif hours <= 72:
                params["daterange"] = 3      # 3 hari terakhir
            elif hours <= 168:
                params["daterange"] = 7      # 7 hari terakhir
            elif hours <= 336:
                params["daterange"] = 14     # 14 hari terakhir
            else:
                params["daterange"] = 30     # 30 hari terakhir
            log.debug(f"Using daterange={params['daterange']} for hours_old={hours}")

        response = self.session.get(url, params=params, allow_redirects=True)

        if response.status_code not in range(200, 400):
            raise JobStreetException(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )

        soup = BeautifulSoup(response.text, "html.parser")

        # JobStreet search result cards
        job_cards = soup.find_all("article")

        log.debug(f"Found {len(job_cards)} job cards on page {page}")

        jobs = []
        for card in job_cards:
            try:
                job = self._parse_card(card)
                if job:
                    jobs.append(job)
            except Exception as e:
                log.warning(f"Failed to parse job card: {e}")
                continue

        return jobs

    def _parse_card(self, card: BeautifulSoup) -> JobPost | None:
        """Parse a single job card into JobPost."""
        # Extract job URL from link overlay or view-job-link
        link_el = (
            card.find(attrs={"data-automation": "job-list-view-job-link"})
            or card.find(attrs={"data-automation": "job-list-item-link-overlay"})
            or card.find("a")
        )
        if not link_el:
            return None

        job_url = link_el.get("href", "")
        if not job_url.startswith("http"):
            job_url = f"https://id.jobstreet.com{job_url}"

        job_id = job_url.split("/")[-1] if "/job/" in job_url else None

        # Title
        title_el = card.find(attrs={"data-automation": "jobTitle"})
        title = title_el.get_text(strip=True) if title_el else None

        # Company
        company_el = card.find(attrs={"data-automation": "jobCompany"})
        company_name = company_el.get_text(strip=True) if company_el else None

        # Location
        location_el = card.find(attrs={"data-automation": "jobLocation"})
        location = parse_location(location_el.get_text(strip=True)) if location_el else Location(
            country="Indonesia"
        )

        # Description (short teaser from search result)
        desc_el = card.find(attrs={"data-automation": "jobShortDescription"})
        description = markdown_converter(str(desc_el)) if desc_el else None

        # Salary
        salary_el = card.find(attrs={"data-automation": "jobSalary"})
        compensation = None
        if salary_el:
            salary_text = salary_el.get_text(strip=True)
            interval, min_amount, max_amount, currency = extract_salary(salary_text)
            if interval:
                compensation = Compensation(
                    interval=CompensationInterval(interval) if interval else None,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    currency=currency,
                )

        # Date posted
        date_el = card.find(attrs={"data-automation": "jobListingDate"})
        date_posted = parse_date_posted(date_el.get_text(strip=True)) if date_el else None

        if not title or not job_url:
            return None

        return JobPost(
            id=job_id,
            title=title,
            company_name=company_name,
            job_url=job_url,
            location=location,
            description=description,
            compensation=compensation,
            date_posted=date_posted,
        )
