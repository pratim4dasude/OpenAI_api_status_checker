import time
import requests
import feedparser
import re
import html
from typing import Optional, Tuple, Set, List, Dict, Any


RSS_FEED_URL = "https://status.openai.com/history.rss"
CHECK_INTERVAL = 10


WEBHOOK_URLS = [
    "http://localhost:8000/webhook",
]

PROVIDER_NAME = "openai"
SOURCE_NAME = "openai-status-rss"


def fetch_rss(
        etag: Optional[str],
        last_modified: Optional[str],
) -> Tuple[Optional[feedparser.FeedParserDict], Optional[str], Optional[str]]:

    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    resp = requests.get(RSS_FEED_URL, headers=headers, timeout=10)

    if resp.status_code == 304:
        return None, etag, last_modified

    resp.raise_for_status()

    new_etag = resp.headers.get("ETag", etag)
    new_last_modified = resp.headers.get("Last-Modified", last_modified)

    feed = feedparser.parse(resp.content)
    return feed, new_etag, new_last_modified


def strip_html(text: str) -> str:

    no_tags = re.sub(r"<[^>]+>", " ", text)
    unescaped = html.unescape(no_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


def extract_status_components_phase(
        summary_html: str,
) -> Tuple[str, List[str], Optional[str]]:

    if not summary_html:
        return "", [], None

    split_parts = re.split(r"<b>Affected components</b>", summary_html, maxsplit=1)
    status_html = split_parts[0]
    components_html = split_parts[1] if len(split_parts) > 1 else ""

    status_text = strip_html(status_html)

    phase = None
    m = re.search(r"Status:\s*([^<]+)", status_html)
    if m:
        phase_raw = strip_html(m.group(1))
        if phase_raw:
            phase = phase_raw.split()[0].strip()

    component_items = re.findall(r"<li>(.*?)</li>", components_html, flags=re.DOTALL)
    components: List[str] = []
    for item in component_items:
        comp_clean = strip_html(item)
        comp_clean = re.sub(r"\s*\(.*\)$", "", comp_clean).strip()
        if comp_clean:
            components.append(comp_clean)

    seen = set()
    deduped = []
    for c in components:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return status_text, deduped, phase


def compute_overall_state(
        feed: Optional[feedparser.FeedParserDict],
) -> Tuple[str, List[str], Optional[str], Optional[str]]:
    if feed is None or not getattr(feed, "entries", None):
        return "operational", [], None, None

    degraded_components: List[str] = []

    for entry in feed.entries:
        summary_html = getattr(entry, "summary", "").strip()
        _, components, phase = extract_status_components_phase(summary_html)
        if phase and phase.lower() != "resolved":
            degraded_components.extend(components)

    seen = set()
    deduped = []
    for c in degraded_components:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    last_incident_time = None
    last_incident_title = None
    if feed.entries:
        latest = feed.entries[0]
        last_incident_time = getattr(latest, "published", None)
        last_incident_title = getattr(latest, "title", None)

    if deduped:
        return "degraded", deduped, last_incident_time, last_incident_title
    else:
        return "operational", [], last_incident_time, last_incident_title


# ------------ WEBHOOK SENDER ------------

def send_webhook(event_type: str, payload: Dict[str, Any]) -> None:
    body = {
        "event": event_type,
        "provider": PROVIDER_NAME,
        "source": SOURCE_NAME,
        **payload,
    }

    for url in WEBHOOK_URLS:
        try:
            resp = requests.post(url, json=body, timeout=5)
            if 200 <= resp.status_code < 300:
                print(f"➡️  Webhook sent to {url} (event={event_type})")
            else:
                print(f"⚠️ Webhook to {url} failed: HTTP {resp.status_code}")
        except Exception as e:
            print(f"⚠️ Webhook to {url} error: {e}")


def main():
    print("🔍 OpenAI Status RSS Watcher (Webhook-enabled)")
    print("🌐 Source:", RSS_FEED_URL)
    print(f"⏱ Refreshing every {CHECK_INTERVAL} seconds…")
    print("Press CTRL+C to exit.\n")

    seen_entries: Set[str] = set()
    etag: Optional[str] = None
    last_modified: Optional[str] = None

    overall_state = "unknown"
    last_overall_state = "unknown"
    impacted_components: List[str] = []
    last_incident_time: Optional[str] = None
    last_incident_title: Optional[str] = None

    try:
        feed, etag, last_modified = fetch_rss(etag, last_modified)
        if feed is not None:
            for entry in feed.entries:
                entry_id = getattr(entry, "id", None) or getattr(entry, "link", None)
                if entry_id:
                    seen_entries.add(entry_id)

            overall_state, impacted_components, last_incident_time, last_incident_title = compute_overall_state(feed)
            last_overall_state = overall_state

            print(f"Initialized watcher. Existing {len(feed.entries)} incidents marked as seen.\n")

            # Startup summary
            print("📌 INITIAL STATUS CHECK")
            print("-------------------------")

            all_components = set()
            for entry in feed.entries:
                _, comps, _ = extract_status_components_phase(entry.summary)
                all_components.update(comps)

            if all_components:
                print("Monitoring OpenAI services (discovered from RSS):")
                for c in sorted(all_components):
                    print(f"- {c}")
            else:
                print("Monitoring OpenAI status page (no components listed in feed).")

            if last_incident_time and last_incident_title:
                print(f"\nLast incident update: {last_incident_time} — {last_incident_title}")

            if overall_state == "operational":
                print("Current state: ✅ All systems operational\n")
            else:
                print("Current state: ⚠️ Degraded")
                print("Impacted components:", ", ".join(impacted_components))

            print("✔️ Live monitoring + webhook dispatch started...")
            print("-----------------------------------------------\n")

    except Exception as e:
        print(f"⚠️ Initial fetch failed: {e}")

    # LIVE LOOP
    while True:
        try:
            feed, etag, last_modified = fetch_rss(etag, last_modified)

            if feed is not None:

                entries = list(feed.entries)[::-1]
                for entry in entries:
                    entry_id = getattr(entry, "id", None) or getattr(entry, "link", None)
                    if not entry_id or entry_id in seen_entries:
                        continue

                    seen_entries.add(entry_id)

                    title = entry.title.strip()
                    published = entry.published.strip()
                    summary_html = entry.summary.strip()

                    status_text, components, phase = extract_status_components_phase(summary_html)
                    products_str = ", ".join(components) if components else title

                    print(f"[{published}] INCIDENT UPDATE")
                    print(f"Incident: {title}")
                    print(f"Products: {products_str}")
                    print(f"Status: {status_text}")
                    if phase:
                        print(f"Phase: {phase}")
                    print("-" * 80)

                    # Webhook event
                    send_webhook(
                        "incident.update",
                        {
                            "incident_title": title,
                            "published_at": published,
                            "phase": phase,
                            "status_text": status_text,
                            "components": components,
                        },
                    )

                overall_state, impacted_components, last_incident_time, last_incident_title = compute_overall_state(
                    feed)

            if overall_state != last_overall_state and overall_state != "unknown":
                print(f"🔄 Status changed: {last_overall_state} → {overall_state}")
                send_webhook(
                    "status.change",
                    {
                        "from_state": last_overall_state,
                        "to_state": overall_state,
                        "impacted_components": impacted_components,
                        "last_incident_title": last_incident_title,
                        "last_incident_time": last_incident_time,
                    },
                )
                last_overall_state = overall_state

            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            status_label = "DEGRADED" if overall_state == "degraded" else "ACTIVE"

            print(f"[{now_str}] {status_label}")
            if last_incident_time and last_incident_title:
                print(f"Last incident update: {last_incident_time} — {last_incident_title}")

            if overall_state == "operational":
                message = "All systems operational (no active incidents detected)."
                print("Current state: ✅ " + message)
            else:
                comps_str = ", ".join(impacted_components) if impacted_components else "Unknown components"
                message = f"Degraded / incident active. Impacted components: {comps_str}"
                print("Current state: ⚠️ " + message)

            #  Heartbeat webhook every interval
            send_webhook(
                "status.heartbeat",
                {
                    "state": overall_state,
                    "status_label": status_label,
                    "timestamp": now_str,
                    "last_incident_title": last_incident_title,
                    "last_incident_time": last_incident_time,
                    "message": message,
                    "impacted_components": impacted_components,
                },
            )

            print()
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 Exiting…")
            break
        except Exception as e:
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now_str}] ⚠️ Error in watcher loop: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
