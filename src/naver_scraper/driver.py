from __future__ import annotations

import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def build_chrome_driver(
    driver_path: str | None = None,
    *,
    headless: bool = False,
    implicit_wait: float = 0,
) -> webdriver.Chrome:
    """Create a Chrome WebDriver without committing driver binaries to Git."""

    resolved_driver_path = driver_path or os.getenv("CHROMEDRIVER_PATH")

    options = Options()
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-dev-shm-usage")
    if headless:
        options.add_argument("--headless=new")

    if resolved_driver_path:
        service = Service(str(Path(resolved_driver_path).expanduser()))
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    if implicit_wait:
        driver.implicitly_wait(implicit_wait)
    return driver
