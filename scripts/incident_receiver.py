#!/usr/bin/env python3
"""
Lightweight Incident & Webhook Receiver Simulator.
Receives Alertmanager webhooks, logs structured incidents, tracks active incidents,
and provides a clean local API / UI view of NOC incidents.
Listens on :9095.
"""

import datetime
import http.server
import json
import os
import socketserver
import threading

PORT = int(os.environ.get("INCIDENT_PORT", 9095))
incidents = []
incident_lock = threading.Lock()

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>NOC Incident Management Center</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; background: #0f141c; color: #d8e2ec; margin: 0; padding: 24px; }
        h1 { color: #58a6ff; font-size: 20px; margin-bottom: 4px; display: flex; align-items: center; gap: 10px; }
        .sub { color: #8b949e; font-size: 13px; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 24px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px 16px; }
        .card-val { font-size: 24px; font-weight: bold; margin-top: 4px; }
        .crit { color: #f85149; }
        .warn { color: #e3b341; }
        .resolved { color: #3fb950; }
        table { width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }
        th, td { text-align: left; padding: 10px 14px; font-size: 13px; border-bottom: 1px solid #21262d; }
        th { background: #1c2128; color: #8b949e; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .badge-critical { background: rgba(248,81,73,0.15); color: #f85149; border: 1px solid #f85149; }
        .badge-warning { background: rgba(227,179,65,0.15); color: #e3b341; border: 1px solid #e3b341; }
        .badge-resolved { background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid #3fb950; }
        .badge-firing { background: rgba(219,109,40,0.2); color: #f0883e; }
        .empty { padding: 30px; text-align: center; color: #8b949e; font-style: italic; }
    </style>
</head>
<body>
    <h1><span>🚨</span> NOC Incident Management Center</h1>
    <div class="sub">Live Alertmanager Webhook Stream & Incident Queue (Auto-refreshes every 5s)</div>
    
    <div class="grid">
        <div class="card">
            <div style="color: #8b949e; font-size: 12px;">Active Incidents</div>
            <div class="card-val warn">{active_count}</div>
        </div>
        <div class="card">
            <div style="color: #8b949e; font-size: 12px;">Critical Incidents</div>
            <div class="card-val crit">{crit_count}</div>
        </div>
        <div class="card">
            <div style="color: #8b949e; font-size: 12px;">Total Processed</div>
            <div class="card-val">{total_count}</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Status</th>
                <th>Severity</th>
                <th>Alert Name</th>
                <th>Node / Target</th>
                <th>Summary & Details</th>
            </tr>
        </thead>
        <tbody>
            {incident_rows}
        </tbody>
    </table>
</body>
</html>
"""

class IncidentServer(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/webhook" or self.path == "/api/alerts":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                received_at = datetime.datetime.now().strftime("%H:%M:%S")
                alerts = data.get("alerts", [])
                with incident_lock:
                    for a in alerts:
                        status = a.get("status", "firing")
                        labels = a.get("labels", {})
                        annotations = a.get("annotations", {})
                        incidents.insert(0, {
                            "time": received_at,
                            "status": status,
                            "alertname": labels.get("alertname", "UnknownAlert"),
                            "severity": labels.get("severity", "info"),
                            "node": labels.get("node", labels.get("instance", "-")),
                            "summary": annotations.get("summary", annotations.get("description", "-")),
                            "startsAt": a.get("startsAt", ""),
                            "endsAt": a.get("endsAt", ""),
                        })
                        if len(incidents) > 100:
                            incidents.pop()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                return
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode())
                return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/incidents":
            with incident_lock:
                active = [i for i in incidents if i["status"] == "firing"]
                crit = [i for i in active if i["severity"] == "critical"]
                rows = []
                if not incidents:
                    rows.append('<tr><td colspan="6" class="empty">No incidents received yet. All systems nominal.</td></tr>')
                for inc in incidents[:30]:
                    status_cls = "badge-resolved" if inc["status"] == "resolved" else "badge-firing"
                    sev_cls = f"badge-{inc['severity']}"
                    rows.append(f"""
                    <tr>
                        <td>{inc['time']}</td>
                        <td><span class="badge {status_cls}">{inc['status']}</span></td>
                        <td><span class="badge {sev_cls}">{inc['severity']}</span></td>
                        <td><strong>{inc['alertname']}</strong></td>
                        <td><code>{inc['node']}</code></td>
                        <td>{inc['summary']}</td>
                    </tr>
                    """)
                html = HTML_TEMPLATE.format(
                    active_count=len(active),
                    crit_count=len(crit),
                    total_count=len(incidents),
                    incident_rows="\n".join(rows)
                )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        elif self.path == "/api/incidents":
            with incident_lock:
                data = json.dumps(incidents)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def main():
    server = socketserver.TCPServer(("0.0.0.0", PORT), IncidentServer)
    print(f"Incident Receiver listening on :{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    main()

