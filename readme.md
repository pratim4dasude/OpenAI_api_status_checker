# 📡 OpenAI Status Monitor
## Real-time Monitoring • Webhook Alerts • Live Dashboard (Gradio)

This project provides a lightweight but powerful system for **monitoring the OpenAI Status Page** in real time.
It detects outages, degradations, and service impacts across models like GPTs, Chat Completions, Sora, Embeddings, Realtime, Image Generation, and more.

The system consists of three components:

1. RSS Watcher – polls OpenAI's RSS feed and sends webhook events (https://status.openai.com/ )
2. Webhook Worker (FastAPI) – receives events and stores the latest status
3. Gradio Dashboard – displays real-time operational and incident information
It runs 24/7 and gives you instant visibility into OpenAI API health.

## 🚀 Features
### ✅ Real-time Status Monitoring

Continuously checks OpenAI's official status feed

Detects outages, degradations, new incidents, and resolved events

### 🌐 Webhook Event System

Sends structured JSON webhook events:

* `incident.update`
* `status.change`
* `status.heartbeat` (every X seconds)

### 📊 Live Dashboard (Gradio)

* Shows current operational state
* Shows latest incident title + timestamp
* Displays heartbeat time
* Shows discovered service/component health
* Auto-refreshes every 5 seconds

### 🧩 Automatic Component Discovery

Dynamically extracts impacted services from the RSS feed.

## 🛠️ Project Structure
```bash
project/
│
├── openai_status_watcher.py     # RSS polling + webhook sender
├── webhook_worker.py            # FastAPI server storing status
├── status_dashboard.py          # Gradio live dashboard
│
└── README.md
```



## 📦 Installation
1. Clone the repo
```commandline
git clone https://github.com/yourname/openai-status-monitor.git
cd openai-status-monitor
```
2. Create & activate virtual environment
```commandline
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
```


3. Install dependencies

```commandline
pip install -r requirements.txt
```

If you don’t yet have a requirements file, these are the needed packages:

```
gradio
fastapi
uvicorn
feedparser
requests
```

## ▶️ Running the System

You must run two processes:

### 1️⃣ Start the Webhook Worker
```commandline
python webhook_worker.py
```

Runs on:
```commandline
http://127.0.0.1:8000
```

Check health:
```commandline
http://127.0.0.1:8000/health
```
### 2️⃣ Start the RSS Watcher
```commandline
python openai_status_watcher.py
```


This script:

* polls the OpenAI RSS feed
* detects incident updates
* sends webhook events
* sends heartbeat status every X seconds

Output example:
```commandline
🔍 OpenAI Status RSS Watcher (Webhook-enabled)
🌐 Source: https://status.openai.com/history.rss
⏱ Refreshing every 10 seconds…
Press CTRL+C to exit.

Initialized watcher. Existing 94 incidents marked as seen.

📌 INITIAL STATUS CHECK
-------------------------
Monitoring OpenAI services (discovered from RSS):
- Agent
- Audio
- Batch
- Chat Completions
- ChatGPT Atlas
- Codex
- Compliance API
- Connectors
- Conversations
- Deep Research
- Embeddings
- Feed
- File uploads
- Files
- Fine-tuning
- GPTs
- Image Generation
- Images
- Login
- Moderations
- Realtime
- Responses
- Search
- Sora
- Video generation
- Video viewing
- Voice mode

Last incident update: Sat, 15 Nov 2025 08:53:03 GMT — Subset of Batch API jobs stuck in finalizing state
Current state: ✅ All systems operational

✔️ Live monitoring + webhook dispatch started...
-----------------------------------------------

[2025-11-16 21:53:56] ACTIVE
Last incident update: Sat, 15 Nov 2025 08:53:03 GMT — Subset of Batch API jobs stuck in finalizing state
Current state: ✅ All systems operational (no active incidents detected).
➡️  Webhook sent to http://localhost:8000/webhook (event=status.heartbeat)
```
### 3️⃣ Launch the Live Dashboard
```commandline
python status_dashboard.py
```

Dashboard opens at:
```commandline
http://127.0.0.1:7860
```
It displays:

* overall status (Active / Degraded)
* last heartbeat
* last incident
* service/component health (if available)

## 🔄 Architecture
```
      OpenAI Status Page (RSS)
                 │
                 ▼
        openai_status_watcher.py
     (Polls RSS, detects incidents,
      sends heartbeat + updates)
                 │
            Webhook POST
                 │
                 ▼
         webhook_worker.py
  (Stores the latest status in memory,
   exposes `/status` endpoint)
                 │
             HTTP GET
                 │
                 ▼
       status_dashboard.py (Gradio)
  (Shows live dashboard, auto-refresh)
```
## 📌 Event Types
`status.heartbeat`

Sent every X seconds:
```json
{
  "event": "status.heartbeat",
  "state": "operational",
  "status_label": "ACTIVE",
  "timestamp": "2025-11-16 20:42:20",
  "last_incident_title": "Subset of Batch API jobs stuck in finalizing state",
  "last_incident_time": "Sat, 15 Nov 2025 08:53:03 GMT",
  "message": "All systems operational.",
  "impacted_components": []
}
```
`incident.update`

Triggered by a new RSS entry:
```json
{
  "event": "incident.update",
  "incident_title": "...",
  "components": ["GPTs", "Chat Completions"],
  "phase": "Investigating"
}
```
`status.change`

Triggered when state flips:

* operational → degraded
* degraded → operational

## 📈 Dashboard Preview

```
🟩 ACTIVE — All systems operational

Internal state: operational | Label: ACTIVE  
Last heartbeat: 2025-11-16 20:42:20  
Message: All systems operational.

Last incident title: Subset of Batch API jobs stuck in finalizing state  
Last incident time: Sat, 15 Nov 2025 08:53:03 GMT  

```
🧪 Test the Webhook
```bash
curl -X POST http://localhost:8000/webhook \
     -H "Content-Type: application/json" \
     -d '{"event": "test", "provider": "local"}'
```

