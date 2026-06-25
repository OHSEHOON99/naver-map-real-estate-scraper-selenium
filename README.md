# Naver Map and Real Estate Scrapers

Python Selenium examples for collecting structured data from Naver Map and
Naver Real Estate.

This repository is maintained as source code only. Browser drivers, raw crawl
outputs, screenshots, and address-level result CSV files are intentionally not
stored in Git.

## What Changed

- Scrapers are packaged as reusable Python modules under `src/naver_scraper/`.
- ChromeDriver is no longer committed. Selenium Manager can resolve the driver
  automatically in recent Selenium versions, or you can pass a local driver path.
- Real crawl outputs are ignored by Git. Tiny synthetic CSV examples live in
  `examples/`.
- The old hard-coded Windows user path was removed.

## Requirements

- Python 3.10+
- Google Chrome
- Network access to the target Naver pages

Install dependencies:

```bash
python -m pip install -e .
```

If you prefer a plain requirements file:

```bash
python -m pip install -r requirements.txt
```

## Usage

Create an output directory first:

```bash
mkdir -p outputs
```

Collect Naver Map cafe search results:

```bash
python -m naver_scraper.naver_map_cafes \
  --query "서초구 카페" \
  --output outputs/cafe_data.csv \
  --max-pages 1
```

Collect Naver Real Estate listings for one administrative area:

```bash
python -m naver_scraper.naver_real_estate \
  --city "서울시" \
  --division "서초구" \
  --section "서초동" \
  --output outputs/real_estate_data.csv \
  --max-complexes 5
```

If Selenium cannot resolve ChromeDriver automatically, pass a local driver:

```bash
python -m naver_scraper.naver_map_cafes \
  --query "서초구 카페" \
  --driver-path "/path/to/chromedriver" \
  --output outputs/cafe_data.csv
```

## Repository Layout

```text
src/naver_scraper/
  driver.py              Chrome driver setup
  naver_map_cafes.py     Naver Map cafe scraper
  naver_real_estate.py   Naver Real Estate listing scraper
examples/
  cafe_data_sample.csv
  real_estate_data_sample.csv
DATA_POLICY.md
```

## Responsible Use

These scripts are for learning and research workflows. Before running them,
review Naver's current terms, robots guidance, and applicable data policies.
Use small request volumes, add delays, and do not republish raw crawl outputs
that may contain address-level listings, business records, or other sensitive
context.

The target pages use dynamic selectors and may change without notice. If a
selector stops working, update the relevant scraper module rather than committing
new raw output files.
