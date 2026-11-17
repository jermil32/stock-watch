"""Alerts (via ntfy) when the watched Extar product option is in stock.

Reads BigCommerce's "instock" flag from the product page and only alerts when the
state changes from out of stock to in stock. Settings come from environment variables:
  NTFY_TOPIC     required: your private ntfy topic name
  EMAIL_ADDRESS  optional: ntfy also forwards the alert to this email
"""
import os
import re
import sys
import urllib.error
import urllib.request

URL = "https://extarusa.com/ep9-mdb/?attributes=eyIxOTkiOiIyNTAiLCIyMDAiOiIyNTIiLCIyMDEiOiIifQ"
STATE_FILE = "last_state.txt"


def fetch_in_stock():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    m = re.search(r'"instock":(true|false)', html)
    if not m:
        raise RuntimeError("Could not find stock flag in page")
    return m.group(1) == "true"


def _post(topic, body, headers):
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=body.encode(), headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=30).close()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ntfy returned {e.code}: {e.read().decode(errors='replace')}") from None


def send_alert(subject, body, click=URL):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("NTFY_TOPIC secret is empty or missing")
    headers = {"Title": subject, "Click": click, "Priority": "high", "Tags": "shopping_cart"}
    email = os.environ.get("EMAIL_ADDRESS", "").strip()
    if email:
        try:
            _post(topic, body, {**headers, "Email": email})
            return
        except RuntimeError as e:
            print(f"Alert with email forwarding failed ({e}); retrying push-only")
    _post(topic, body, headers)


def main():
    if "--test-email" in sys.argv:
        send_alert("Stock checker test", "Alert setup works.")
        print("Test sent.")
        return

    try:
        in_stock = fetch_in_stock()
    except Exception as e:  # transient site errors shouldn't fail the run
        print(f"ERROR fetching page: {e}")
        return

    was = os.path.exists(STATE_FILE) and open(STATE_FILE).read().strip() == "1"
    print(f"in_stock={in_stock} was={was}")

    if in_stock and not was:
        send_alert("Extar EP9 is IN STOCK", f"It looks available:\n{URL}")  # raises on failure, so we retry next run

    with open(STATE_FILE, "w") as f:
        f.write("1" if in_stock else "0")


if __name__ == "__main__":
    main()
