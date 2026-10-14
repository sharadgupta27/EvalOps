"""Tiny webhook receiver for local Alertmanager testing. Standard library only.

Prints one JSON line per alert: receiver path, status, alert name, severity and summary.
Stands in for Slack or PagerDuty so routing can be verified without external accounts.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = min(int(self.headers.get("Content-Length", 0)), 1_000_000)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        for alert in payload.get("alerts", []):
            labels = alert.get("labels", {})
            line = {
                "receiver": self.path.strip("/"),
                "status": alert.get("status"),
                "alertname": labels.get("alertname"),
                "severity": labels.get("severity"),
                "summary": alert.get("annotations", {}).get("summary"),
                "startsAt": alert.get("startsAt"),
            }
            print(json.dumps(line), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # one line per alert above is enough


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()  # noqa: S104 (container-internal)
