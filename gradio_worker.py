import gradio as gr
import requests

STATUS_API_URL = "http://localhost:8000/status"


def fetch_status():
    try:
        resp = requests.get(STATUS_API_URL, timeout=3)
        data = resp.json()
    except Exception as e:
        return (
            "❌ Cannot reach webhook worker",
            f"Error: `{e}`",
            "_No incident data available._",
            "",
        )

    if not data.get("available", False):
        return (
            "⏳ Waiting for first heartbeat…",
            "Make sure the RSS watcher is running and sending `status.heartbeat` webhooks.",
            "_No incident data available._",
            "",
        )

    latest = data.get("latest_status", {})
    known_components = data.get("known_components", [])

    state = latest.get("state", "unknown")
    label = latest.get("status_label", "UNKNOWN")
    ts = latest.get("timestamp", "N/A")
    last_title = latest.get("last_incident_title") or "None"
    last_time = latest.get("last_incident_time") or "None"
    message = latest.get("message", "")
    impacted_components = latest.get("impacted_components", [])

    if state == "operational":
        headline = "🟩 **ACTIVE — All systems operational**"
    elif state == "degraded":
        headline = "🟨 **DEGRADED — Some services are impacted**"
    else:
        headline = "⬜ **UNKNOWN — No status yet**"

    summary_md = (
        f"**Internal state:** `{state}` | **Label:** `{label}`  \n"
        f"**Last heartbeat:** `{ts}`  \n\n"
        f"**Message:** {message or '_No status message provided._'}"
    )

    incident_md = (
        f"**Last incident title:** {last_title}  \n"
        f"**Last incident time:** `{last_time}`"
    )

    if not known_components:
        components_md = ""
    else:
        rows = []
        impacted_set = set(impacted_components)

        for comp in sorted(known_components):
            status_badge = "⚠️ Impacted" if comp in impacted_set else "✅ OK"
            rows.append(f"| {comp} | {status_badge} |")

        header = "| Service / Component | Status |\n|---|---|"
        summary_line = (
            f"**Total services:** {len(known_components)} "
            f"• **Impacted:** {len(impacted_set)} "
            f"• **Healthy:** {len(known_components) - len(impacted_set)}"
        )

        components_md = summary_line + "\n\n" + header + "\n" + "\n".join(rows)

    return headline, summary_md, incident_md, components_md


with gr.Blocks(theme="soft") as demo:
    gr.Markdown("## OpenAI Status Dashboard (Live)")

    with gr.Row():
        headline = gr.Markdown()

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### Overall Status")
            details = gr.Markdown()

        with gr.Column(scale=2):
            gr.Markdown("### ---- Latest Incident ----")
            incident = gr.Markdown()

    components = gr.Markdown(visible=True)

    demo.load(fn=fetch_status, outputs=[headline, details, incident, components])

    timer = gr.Timer(5)
    timer.tick(fn=fetch_status, outputs=[headline, details, incident, components])

if __name__ == "__main__":
    demo.launch()
