#!/usr/bin/env python3
"""Agent d'envoi des passages d'un lecteur d'empreintes vers Ruche RH.

Usage (le lecteur écrit ses passages dans un fichier CSV « identifiant,horodatage ISO ») :

    RUCHE_URL=https://rh.mon-domaine.bj RUCHE_KEY=rr_xxx python3 lecteur_agent.py passages.csv

Chaque ligne du fichier est envoyée une seule fois (la position lue est mémorisée dans passages.csv.pos).
Sans argument, l'agent lit l'entrée standard : « 12 » ou « 12,2026-03-02T07:58:00+01:00 ».

Pour un terminal ZKTeco, remplacez read_lines() par une lecture via la bibliothèque « pyzk »
(conn.get_attendance() renvoie l'identifiant et la date de chaque passage).
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("RUCHE_URL", "").rstrip("/") + "/biometrie/api/lecteur/"
KEY = os.environ.get("RUCHE_KEY", "")


def send(user_id, timestamp=None):
    body = {"user_id": user_id}
    if timestamp:
        body["timestamp"] = timestamp
    req = urllib.request.Request(URL, json.dumps(body).encode(), {
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def read_lines(path):
    if not path:
        yield from sys.stdin
        return
    pos_file = path + ".pos"
    start = int(open(pos_file).read()) if os.path.exists(pos_file) else 0
    with open(path) as fh:
        fh.seek(start)
        for line in fh:
            yield line
        open(pos_file, "w").write(str(fh.tell()))


def main():
    if not KEY or URL == "/biometrie/api/lecteur/":
        sys.exit("Définissez RUCHE_URL et RUCHE_KEY.")
    for line in read_lines(sys.argv[1] if len(sys.argv) > 1 else None):
        parts = [p.strip() for p in line.strip().split(",")]
        if not parts or not parts[0]:
            continue
        status, data = send(parts[0], parts[1] if len(parts) > 1 else None)
        print(status, parts[0], data.get("message", data))


if __name__ == "__main__":
    main()
