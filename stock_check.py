"""Emails when the watched Extar product option is in stock.

Reads BigCommerce's "instock" flag from the product page and only alerts when the
state changes from out of stock to in stock. Secrets come from environment variables.
"""
import os
import re
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage

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


def send_email(subject, body):
    address = os.environ["EMAIL_ADDRESS"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = msg["To"] = address
    msg.set_content(body)
    with smtplib.SMTP("smtp-mail.outlook.com", 587, timeout=30) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(address, os.environ["SMTP_APP_PASSWORD"])
        s.send_message(msg)


def send_ntfy(subject, body):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=body.encode(),
        headers={"Title": subject, "Click": URL}, method="POST")
    urllib.request.urlopen(req, timeout=30).close()


def main():
    if "--test-email" in sys.argv:
        send_email("Stock checker test", "Email setup works.")
        send_ntfy("Stock checker test", "Push setup works.")
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
        subject, body = "Extar EP9 is IN STOCK", f"It looks available:\n{URL}"
        send_email(subject, body)  # raises on failure, so state isn't saved and we retry
        send_ntfy(subject, body)

    with open(STATE_FILE, "w") as f:
        f.write("1" if in_stock else "0")


if __name__ == "__main__":
    main()
