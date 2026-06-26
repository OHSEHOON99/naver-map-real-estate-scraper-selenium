from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

from naver_scraper.driver import build_chrome_driver


NAVER_MAP_SEARCH_URL = "https://map.naver.com/v5/search"


@dataclass
class CafeRecord:
    name: str
    type: str
    reviews: str
    address: str
    business_hours: str
    packaging_available: bool
    pet_friendly: bool
    menus: str


def wait_for_css(driver: WebDriver, css_selector: str, timeout: int = 10) -> Any:
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
    )


def switch_frame(driver: WebDriver, frame_name: str) -> None:
    driver.switch_to.default_content()
    driver.switch_to.frame(frame_name)


def page_down(driver: WebDriver, count: int) -> None:
    body = driver.find_element(By.CSS_SELECTOR, "body")
    body.click()
    for _ in range(count):
        body.send_keys(Keys.PAGE_DOWN)


def safe_get_texts(element: Any, css_selector: str, default: str = "") -> str | list[str]:
    try:
        elements = element.find_elements(By.CSS_SELECTOR, css_selector)
    except Exception:
        return default

    if not elements:
        return default
    if len(elements) == 1:
        return elements[0].text
    return [item.text for item in elements]


def as_text(value: str | list[str] | None, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return " | ".join(item for item in value if item)
    return value or default


def extract_cafe_info(driver: WebDriver, max_attempts: int = 5) -> CafeRecord:
    business_hours: list[dict[str, str]] = []
    menus: list[str] = []
    packaging_available = False
    pet_friendly = False

    name = as_text(
        WebDriverWait(driver, 10).until(lambda d: safe_get_texts(d, ".GHAhO")),
        "unknown",
    )
    cafe_type = as_text(
        WebDriverWait(driver, 10).until(lambda d: safe_get_texts(d, ".lnJFt")),
        "unknown",
    )
    reviews = as_text(
        WebDriverWait(driver, 10).until(lambda d: safe_get_texts(d, ".PXMot")),
        "unknown",
    )
    address = as_text(
        WebDriverWait(driver, 10).until(lambda d: safe_get_texts(d, "span.LDgIH")),
        "unknown",
    )

    try:
        expand_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.gKP9i.RMgN0"))
        )
        expand_button.click()
        day_elements = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.w9QyJ"))
        )
        for day_element in day_elements:
            day_name = as_text(safe_get_texts(day_element, "span.i8cJw"), "unknown")
            hours_info = as_text(safe_get_texts(day_element, "div.H3ua4"), "unknown")
            business_hours.append({"day": day_name, "hours": hours_info})
    except TimeoutException:
        business_hours.append({"day": "unknown", "hours": "unknown"})

    for _ in range(max_attempts):
        if not menus:
            for item_selector, text_selector in (
                ("li.ipNNM", "span.VQvNX"),
                ("li.gHmZ_", "a.ihmWt"),
            ):
                menu_items = driver.find_elements(By.CSS_SELECTOR, item_selector)
                if menu_items:
                    menus = [
                        as_text(safe_get_texts(item, text_selector), "unknown")
                        for item in menu_items
                    ]
                    break

        features_text = as_text(safe_get_texts(driver, "div.xPvPE"))
        packaging_available = "포장" in features_text
        pet_friendly = "반려동물 동반" in features_text

        if menus:
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

    return CafeRecord(
        name=name,
        type=cafe_type,
        reviews=reviews,
        address=address,
        business_hours=json.dumps(business_hours, ensure_ascii=False),
        packaging_available=packaging_available,
        pet_friendly=pet_friendly,
        menus=json.dumps(menus or ["unknown"], ensure_ascii=False),
    )


def save_records(records: list[CafeRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [field.name for field in CafeRecord.__dataclass_fields__.values()]
    rows = [asdict(record) for record in records]
    pd.DataFrame(rows, columns=columns).to_csv(output_path, index=False)


def scrape_cafes(
    *,
    query: str,
    output_path: Path,
    driver_path: str | None = None,
    headless: bool = False,
    max_pages: int = 1,
    page_down_count: int = 40,
    min_delay: float = 1.0,
    max_delay: float = 3.0,
) -> list[CafeRecord]:
    driver = build_chrome_driver(driver_path, headless=headless)
    records: list[CafeRecord] = []

    try:
        driver.get(NAVER_MAP_SEARCH_URL)
        wait_for_css(driver, "div.input_box > input.input_search")
        search = driver.find_element(By.CSS_SELECTOR, "div.input_box > input.input_search")
        search.send_keys(query)
        search.send_keys(Keys.ENTER)
        time.sleep(1)

        switch_frame(driver, "searchIframe")
        page_down(driver, page_down_count)
        time.sleep(2)

        page_buttons = driver.find_elements(By.CSS_SELECTOR, ".zRM9F > a")
        available_pages = max(1, len(page_buttons))
        target_pages = min(max_pages, available_pages)

        for page_index in range(target_pages):
            cafe_items = driver.find_elements(By.CSS_SELECTOR, "li.UEzoS")
            filtered_items = [
                item
                for item in cafe_items
                if "UEzoS rTjJo" in item.get_attribute("class")
                and "cZnHG" not in item.get_attribute("class")
            ]

            for cafe in tqdm(filtered_items, desc=f"Page {page_index + 1}", leave=False):
                try:
                    WebDriverWait(cafe, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.tzwk0"))
                    ).click()
                    time.sleep(random.uniform(min_delay, max_delay))
                    switch_frame(driver, "entryIframe")
                    records.append(extract_cafe_info(driver))
                    switch_frame(driver, "searchIframe")
                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception as exc:
                    print(f"Skipping one cafe result: {exc}")
                    switch_frame(driver, "searchIframe")

            if page_index + 1 >= target_pages:
                break

            page_buttons = driver.find_elements(By.CSS_SELECTOR, ".zRM9F > a")
            if page_index + 1 < len(page_buttons):
                page_buttons[page_index + 1].click()
                time.sleep(2)

        save_records(records, output_path)
        return records
    finally:
        driver.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape cafe search results from Naver Map.")
    parser.add_argument("--query", required=True, help='Search query, for example "서초구 카페".')
    parser.add_argument("--output", required=True, type=Path, help="CSV output path.")
    parser.add_argument("--driver-path", help="Optional ChromeDriver path.")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode.")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum search result pages.")
    parser.add_argument("--page-down-count", type=int, default=40, help="Scroll count per page.")
    parser.add_argument("--min-delay", type=float, default=1.0, help="Minimum delay between actions.")
    parser.add_argument("--max-delay", type=float, default=3.0, help="Maximum delay between actions.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = scrape_cafes(
        query=args.query,
        output_path=args.output,
        driver_path=args.driver_path,
        headless=args.headless,
        max_pages=args.max_pages,
        page_down_count=args.page_down_count,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )
    print(f"Saved {len(records)} cafe records to {args.output}")


if __name__ == "__main__":
    main()
