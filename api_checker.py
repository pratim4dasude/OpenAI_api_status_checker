import time
import requests
import feedparser
import re
import html
from typing import Optional, Tuple, Set, List

RSS_FEED_URL = "https://status.openai.com/history.rss"
CHECK_INTERVAL = 3


def fetch_rss(etag: Optional[str], last_modified: Optional[str]):
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


def extract_status_components_phase(summary_html: str):
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
    components = []
    for item in component_items:
        comp_clean = strip_html(item)
        comp_clean = re.sub(r"\s*\(.*\)$", "", comp_clean).strip()
        if comp_clean:
            components.append(comp_clean)

    # dedupe
    seen = set()
    deduped = []
    for c in components:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return status_text, deduped, phase


def compute_overall_state(feed):
    if feed is None or not getattr(feed, "entries", None):
        return "operational", [], None, None

    degraded_components = []

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


def main():
    print("🔍 OpenAI Status RSS Watcher Started")
    print("🌐 Source:", RSS_FEED_URL)
    print(f"⏱ Refreshing every {CHECK_INTERVAL} seconds…")
    print("Press CTRL+C to exit.\n")

    seen_entries = set()
    etag = None
    last_modified = None

    overall_state = "unknown"
    impacted_components = []
    last_incident_time = None
    last_incident_title = None

    # INITIAL FETCH
    try:
        feed, etag, last_modified = fetch_rss(etag, last_modified)

        if feed is not None:
            for entry in feed.entries:
                entry_id = getattr(entry, "id", None) or getattr(entry, "link", None)
                if entry_id:
                    seen_entries.add(entry_id)

            overall_state, impacted_components, last_incident_time, last_incident_title = compute_overall_state(feed)
            print(f"Initialized watcher. Existing {len(feed.entries)} incidents marked as seen.\n")

            # ---------------------------------------
            # NEW: Startup SUMMARY BLOCK
            # ---------------------------------------
            print("📌 INITIAL STATUS CHECK")
            print("-------------------------")

            # Collect components from feed
            all_components = set()
            for entry in feed.entries:
                _, comps, _ = extract_status_components_phase(entry.summary)
                for c in comps:
                    all_components.add(c)

            if all_components:
                print("Monitoring OpenAI services:")
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

            print("✔️ Live monitoring started...")
            print("---------------------------------\n")

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

                    print(f"[{published}]")
                    print(f"Incident: {title}")
                    print(f"Products: {products_str}")
                    print(f"Status: {status_text}")
                    if phase:
                        print(f"Phase: {phase}")
                    print("-" * 80)

                overall_state, impacted_components, last_incident_time, last_incident_title = compute_overall_state(feed)

            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            status_label = "DEGRADED" if overall_state == "degraded" else "ACTIVE"

            print(f"[{now_str}] {status_label}")

            if last_incident_time and last_incident_title:
                print(f"Last incident update: {last_incident_time} — {last_incident_title}")

            if overall_state == "operational":
                print("Current state: ✅ All systems operational (no active incidents detected).")
            else:
                print("Current state: ⚠️ Degraded / incident active.")
                print("Impacted components:", ", ".join(impacted_components))

            print()
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 Exiting…")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
