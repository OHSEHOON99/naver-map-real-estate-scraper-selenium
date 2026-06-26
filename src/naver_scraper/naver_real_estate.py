from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

from naver_scraper.driver import build_chrome_driver


NAVER_REAL_ESTATE_URL = "https://land.naver.com/"


def click_when_ready(driver: WebDriver, by: str, selector: str, timeout: int = 10) -> None:
    WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, selector))).click()


def choose_region(driver: WebDriver, *, city: str, division: str, section: str) -> None:
    click_when_ready(driver, By.CSS_SELECTOR, "a.list", timeout=10)
    click_when_ready(
        driver,
        By.XPATH,
        f"//a[contains(@class, '_cityItm') and normalize-space(text())='{city}']",
        timeout=10,
    )
    click_when_ready(
        driver,
        By.XPATH,
        f"//a[contains(@class, '_dvsnItm') and normalize-space(text())='{division}']",
        timeout=10,
    )
    click_when_ready(
        driver,
        By.XPATH,
        f"//a[contains(@class, '_secItm') and normalize-space(text())='{section}']",
        timeout=10,
    )
    click_when_ready(
        driver,
        By.XPATH,
        "//a[contains(@class, 'NPI=a: view') and normalize-space(text())='확인 매물 보기']",
        timeout=10,
    )


def extract_text(element: WebElement, by: str, selector: str, default: str = "") -> str:
    try:
        return element.find_element(by, selector).text.strip()
    except Exception:
        return default


def extract_listing_info(driver: WebDriver) -> dict[str, Any]:
    data: dict[str, Any] = {}

    try:
        title_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "info_title_wrap"))
        )
        data["title"] = extract_text(title_element, By.CLASS_NAME, "info_title_name")
    except Exception:
        data["title"] = ""

    try:
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "info_article_price"))
        )
        data["deal_type"] = extract_text(price_element, By.CLASS_NAME, "type")
        data["price"] = extract_text(price_element, By.CLASS_NAME, "price")
    except Exception:
        data["deal_type"] = ""
        data["price"] = ""

    try:
        table_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "info_table_wrap"))
        )
        soup = BeautifulSoup(table_element.get_attribute("outerHTML"), "html.parser")
        for row in soup.find_all("tr", class_="info_table_item"):
            headers = row.find_all("th", class_="table_th")
            values = row.find_all("td", class_="table_td")
            for header, value in zip(headers, values):
                key = header.get_text(strip=True)
                if key in {"중개사", "매물설명"}:
                    continue
                text = value.get_text(strip=True)
                if key == "관리비":
                    text = text.replace("상세보기", "").strip()
                data[key] = text
    except Exception as exc:
        print(f"Listing table extraction failed: {exc}")

    try:
        image_element = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CLASS_NAME, "floor_plan_img"))
        )
        data["image_url"] = image_element.find_element(By.TAG_NAME, "img").get_attribute("src")
    except TimeoutException:
        data["image_url"] = ""
    except Exception:
        data["image_url"] = ""

    return data


def find_complex_buttons(driver: WebDriver) -> list[str]:
    buttons = WebDriverWait(driver, 5).until(
        lambda d: [
            button
            for button in d.find_elements(
                By.CSS_SELECTOR, "a.marker_complex--apart[role='button']"
            )
            if "is-small" not in button.get_attribute("class")
        ]
    )
    return [button.get_attribute("id") or button.text for button in buttons if button]


def collect_item_links(driver: WebDriver) -> list[WebElement]:
    item_elements = WebDriverWait(driver, 10).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, "div.item")
    )
    links: list[WebElement] = []
    for item in item_elements:
        if "item_inner--agent" in item.get_attribute("class"):
            continue
        if item.find_elements(By.CSS_SELECTOR, "a.label--cp"):
            continue
        try:
            links.append(item.find_element(By.CSS_SELECTOR, "a.item_link"))
        except Exception:
            continue
    return links


def get_complex_address(driver: WebDriver) -> str:
    try:
        click_when_ready(
            driver,
            By.XPATH,
            "//button[contains(text(), '단지정보') and contains(@class, 'complex_link')]",
            timeout=10,
        )
        return WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "address"))
        ).text
    except Exception:
        return ""


def close_detail_panel(driver: WebDriver) -> None:
    try:
        click_when_ready(
            driver,
            By.XPATH,
            "//button[@class='btn_close' and @aria-label='상세페이지 닫기']",
            timeout=2,
        )
    except Exception:
        pass


def save_records(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(output_path, index=False)


def scrape_real_estate(
    *,
    city: str,
    division: str,
    section: str,
    output_path: Path,
    driver_path: str | None = None,
    headless: bool = False,
    max_complexes: int | None = None,
    action_delay: float = 0.5,
) -> list[dict[str, Any]]:
    driver = build_chrome_driver(driver_path, headless=headless)
    records: list[dict[str, Any]] = []

    try:
        driver.get(NAVER_REAL_ESTATE_URL)
        choose_region(driver, city=city, division=division, section=section)
        click_when_ready(driver, By.ID, "type6", timeout=10)
        time.sleep(5)

        complex_ids = find_complex_buttons(driver)
        if max_complexes is not None:
            complex_ids = complex_ids[:max_complexes]

        for complex_id in tqdm(complex_ids, desc="Complexes"):
            try:
                button = WebDriverWait(driver, 5).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, f"a[id='{complex_id}']")
                )
                driver.execute_script("arguments[0].click();", button)
                item_links = collect_item_links(driver)
                if not item_links:
                    continue

                address = get_complex_address(driver)
                for link in item_links:
                    try:
                        time.sleep(action_delay)
                        link.click()
                        record = extract_listing_info(driver)
                        record["address"] = address
                        records.append(record)
                    except Exception as exc:
                        print(f"Skipping one listing: {exc}")
                        continue
                close_detail_panel(driver)
            except Exception as exc:
                print(f"Skipping complex {complex_id}: {exc}")
                continue

        save_records(records, output_path)
        return records
    finally:
        driver.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape listings from Naver Real Estate.")
    parser.add_argument("--city", required=True, help='City label, for example "서울시".')
    parser.add_argument("--division", required=True, help='Division label, for example "서초구".')
    parser.add_argument("--section", required=True, help='Section label, for example "서초동".')
    parser.add_argument("--output", required=True, type=Path, help="CSV output path.")
    parser.add_argument("--driver-path", help="Optional ChromeDriver path.")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode.")
    parser.add_argument("--max-complexes", type=int, help="Limit the number of complexes.")
    parser.add_argument("--action-delay", type=float, default=0.5, help="Delay between listing clicks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = scrape_real_estate(
        city=args.city,
        division=args.division,
        section=args.section,
        output_path=args.output,
        driver_path=args.driver_path,
        headless=args.headless,
        max_complexes=args.max_complexes,
        action_delay=args.action_delay,
    )
    print(f"Saved {len(records)} listings to {args.output}")


if __name__ == "__main__":
    main()
