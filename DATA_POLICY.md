# Data Policy

This repository stores scraper source code and tiny synthetic examples only.

Do not commit:

- raw Naver Map or Naver Real Estate crawl outputs
- address-level listing exports
- screenshots that may contain personal or account context
- browser driver binaries
- cookies, tokens, credentials, or local `.env` files

Write local crawl results to `outputs/` or another ignored directory. If a
small fixture is useful for documentation, place a synthetic example under
`examples/` and avoid using real listings, real businesses, or live service
responses.

Note: removing files from the latest commit does not remove them from old Git
history. If previously committed data must be purged from history, perform a
separate history rewrite with a tool such as `git filter-repo`, then rotate any
exposed credentials if applicable.
