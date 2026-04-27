import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

# ── Config — reads from GitHub Secrets (never hardcode passwords) ──────────────
SENDER_EMAIL    = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT       = os.getenv("RECIPIENT_EMAIL")

CXODRIVE_URL  = "https://cxodrive.com/"
ETCFO_URL     = "https://cfo.economictimes.indiatimes.com/tag/appointments"
ETCFO_DOMAIN  = "https://cfo.economictimes.indiatimes.com"


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 1 — CXO Drive
# ══════════════════════════════════════════════════════════════════════════════

def scrape_cxodrive(page):
    print("\n── CXO Drive ────────────────────────────────────────────────")
    page.goto(CXODRIVE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    cards = page.locator("div.rounded-2xl.bg-card.border.border-border").all()
    print(f"  Total cards on page: {len(cards)}")

    results = []
    for card in cards:
        try:
            tag_els = card.locator("span.text-secondary.font-medium").all()
            is_joining = any(
                "joining announcement" in t.inner_text().strip().lower()
                for t in tag_els
            )
        except:
            is_joining = False

        if not is_joining:
            continue

        try:
            header1   = card.locator("p.font-semibold.text-foreground.text-sm").first.inner_text().strip()
            header2   = card.locator("p.text-xs.text-muted-foreground").first.inner_text().strip()
            body_text = card.locator("p.text-sm.text-foreground\\/80.leading-relaxed.mb-4").first.inner_text().strip()

            results.append({
                "source":  "CXO Drive",
                "type":    "cxo",
                "header1": header1,
                "header2": header2,
                "body":    body_text,
                "author":  "",
                "date":    "",
                "url":     CXODRIVE_URL
            })
            print(f"  ✅ {header1} | {header2}")
        except Exception as e:
            print(f"  ⚠️  Skipped card: {e}")

    print(f"  → {len(results)} joining announcement(s) found")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 2 — ET CFO
# ══════════════════════════════════════════════════════════════════════════════

def get_etcfo_links(page):
    page.goto(ETCFO_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    hrefs = []

    try:
        for el in page.locator("li.top-story-panel__item.spotlight.story a[href]").all():
            href = el.get_attribute("href") or ""
            if "/news/" in href:
                path = "/news/" + href.split("/news/")[-1]
                full = ETCFO_DOMAIN + path
                if full not in hrefs:
                    hrefs.append(full)
                    print(f"  [spotlight] {full}")
                break
    except Exception as e:
        print(f"  ⚠️  Spotlight: {e}")

    try:
        for el in page.locator("li.top-story-panel__item.story:not(.spotlight) a.top-story-panel__link[href]").all():
            href = el.get_attribute("href") or ""
            if "/news/" in href:
                path = "/news/" + href.split("/news/")[-1]
                full = ETCFO_DOMAIN + path
                if full not in hrefs:
                    hrefs.append(full)
                    print(f"  [story]     {full}")
    except Exception as e:
        print(f"  ⚠️  Stories: {e}")

    print(f"  → {len(hrefs)} link(s) found")
    return hrefs


def scrape_etcfo_article(page, url):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
    except Exception as e:
        print(f"  ⚠️  Could not load {url}: {e}")
        return None

    title = "N/A"
    try:
        title = page.locator("h1").first.inner_text(timeout=6000).strip()
    except:
        pass

    synopsis = "N/A"
    for sel in ["span.detail_synopsis", "div.sponsor_section_detail span", "h3.desktop-view"]:
        try:
            s = page.locator(sel).first.inner_text(timeout=5000).strip()
            if s:
                synopsis = s
                break
        except:
            pass

    authors = []
    try:
        for el in page.locator("a.author-info-popup").all():
            n = el.inner_text(timeout=3000).strip()
            if n and n not in authors:
                authors.append(n)
    except:
        pass
    try:
        for el in page.locator("a[href*='/agency/']").all():
            n = el.inner_text(timeout=3000).strip()
            if n and n not in authors:
                authors.append(n)
    except:
        pass

    date = "N/A"
    for sel in ["li:has-text('Updated On')", "li:has-text('Published On')"]:
        try:
            d = page.locator(sel).first.inner_text(timeout=5000).strip()
            if d:
                date = d
                break
        except:
            pass

    print(f"  ✅ {title[:75]}")
    return {
        "source":  "ET CFO",
        "type":    "etcfo",
        "header1": title,
        "header2": "",
        "body":    synopsis,
        "author":  " | ".join(authors) if authors else "N/A",
        "date":    date,
        "url":     url
    }


def scrape_etcfo(page):
    print("\n── ET CFO ───────────────────────────────────────────────────")
    hrefs = get_etcfo_links(page)
    results = []
    for url in hrefs:
        article = scrape_etcfo_article(page, url)
        if article:
            results.append(article)
    print(f"  → {len(results)} article(s) scraped")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  EMAIL CARDS
# ══════════════════════════════════════════════════════════════════════════════

def build_cxo_card(index, item):
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="
        border:1px solid #ddd6fe; border-radius:12px;
        margin-bottom:20px; background-color:#ffffff;
        font-family:Calibri,Arial,sans-serif;">
        <tr>
            <td style="padding:18px 22px 10px 22px;">
                <p style="font-size:11px;font-weight:700;color:#7c3aed;
                           text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0;">
                    🚀 Joining Announcement #{index}
                </p>
                <h2 style="font-size:20px;font-weight:700;color:#1a1a1a;margin:0 0 4px 0;">
                    {item['header1']}
                </h2>
                <h3 style="font-size:14px;font-weight:500;color:#6b7280;margin:0 0 12px 0;">
                    {item['header2']}
                </h3>
                <p style="font-size:13px;color:#374151;line-height:1.7;margin:0;">
                    {item['body']}
                </p>
            </td>
        </tr>
        <tr>
            <td style="padding:10px 22px;background:#f5f3ff;
                       border-top:1px solid #ddd6fe;font-size:12px;color:#7c3aed;">
                Source: <a href="{CXODRIVE_URL}" style="color:#7c3aed;text-decoration:none;">CXO Drive</a>
            </td>
        </tr>
    </table>"""


def build_etcfo_card(index, item):
    author_date = ""
    if item['author'] != "N/A" or item['date'] != "N/A":
        author_date = f"""
        <p style="font-size:12px;color:#6b7280;margin:0 0 6px 0;">
            ✍️ <strong>{item['author']}</strong> &nbsp;|&nbsp; 🕒 {item['date']}
        </p>"""
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="
        border:1px solid #fee2e2; border-radius:12px;
        margin-bottom:20px; background-color:#ffffff;
        font-family:Calibri,Arial,sans-serif;">
        <tr>
            <td style="padding:18px 22px 10px 22px;">
                <p style="font-size:11px;font-weight:700;color:#c0392b;
                           text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0;">
                    📰 ET CFO Story #{index}
                </p>
                <h2 style="font-size:20px;font-weight:700;color:#1a1a1a;margin:0 0 12px 0;">
                    {item['header1']}
                </h2>
                <p style="font-size:13px;color:#374151;line-height:1.7;margin:0 0 12px 0;">
                    {item['body']}
                </p>
            </td>
        </tr>
        <tr>
            <td style="padding:10px 22px;background:#fff5f5;border-top:1px solid #fee2e2;">
                {author_date}
                <a href="{item['url']}" style="font-size:12px;color:#c0392b;text-decoration:none;">
                    Read full article →
                </a>
            </td>
        </tr>
    </table>"""


# ══════════════════════════════════════════════════════════════════════════════
#  SEND EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_combined_email(cxo_items, etcfo_items):
    if len(cxo_items) + len(etcfo_items) == 0:
        print("⚠️  Nothing scraped. Email not sent.")
        return

    cxo_section = ""
    if cxo_items:
        cards = "".join(build_cxo_card(i + 1, x) for i, x in enumerate(cxo_items))
        cxo_section = f"""
        <tr><td style="padding:10px 0 4px 0;">
            <h2 style="font-size:16px;font-weight:700;color:#7c3aed;
                        border-left:4px solid #7c3aed;padding-left:10px;margin:0 0 16px 0;">
                CXO Drive — Joining Announcements ({len(cxo_items)})
            </h2>{cards}
        </td></tr>"""

    etcfo_section = ""
    if etcfo_items:
        cards = "".join(build_etcfo_card(i + 1, x) for i, x in enumerate(etcfo_items))
        etcfo_section = f"""
        <tr><td style="padding:10px 0 4px 0;">
            <h2 style="font-size:16px;font-weight:700;color:#c0392b;
                        border-left:4px solid #c0392b;padding-left:10px;margin:0 0 16px 0;">
                ET CFO — Top Stories ({len(etcfo_items)})
            </h2>{cards}
        </td></tr>"""

    html = f"""
    <html><body style="font-family:Calibri,Arial,sans-serif;
                        background-color:#f4f4f4;padding:30px;margin:0;">
        <table width="680" cellpadding="0" cellspacing="0" align="center">
            <tr>
                <td style="background-color:#1a1a2e;padding:28px 24px;
                            border-radius:12px 12px 0 0;text-align:center;">
                    <h1 style="color:#ffffff;font-size:22px;margin:0;letter-spacing:1px;">
                        📢 CFO ANNOUNCEMENT
                    </h1>
                    <p style="color:#aaaaaa;font-size:13px;margin:8px 0 0 0;">
                        {len(cxo_items)} CXO Drive post(s) &nbsp;|&nbsp; {len(etcfo_items)} ET CFO article(s)
                    </p>
                </td>
            </tr>
            <tr>
                <td style="padding:28px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        {cxo_section}
                        {etcfo_section}
                    </table>
                </td>
            </tr>
            <tr>
                <td style="border-top:1px solid #dddddd;padding:20px 0;text-align:center;">
                    <p style="font-size:12px;color:#888888;margin:0 0 8px 0;">Sources:</p>
                    <a href="{CXODRIVE_URL}" style="font-size:12px;color:#7c3aed;
                        text-decoration:none;margin-right:20px;">cxodrive.com</a>
                    <a href="{ETCFO_URL}" style="font-size:12px;color:#c0392b;
                        text-decoration:none;">cfo.economictimes.indiatimes.com</a>
                </td>
            </tr>
        </table>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CFO ANNOUNCEMENT"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT, msg.as_string())

    print(f"✅ Email sent — {len(cxo_items)} CXO + {len(etcfo_items)} ETCFO → {RECIPIENT}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        page = context.new_page()

        cxo_items   = scrape_cxodrive(page)
        etcfo_items = scrape_etcfo(page)
        browser.close()

    send_combined_email(cxo_items, etcfo_items)