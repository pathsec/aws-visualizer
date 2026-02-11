#!/usr/bin/env python3
"""
AWS Inventory Visualizer — Flask Server
========================================
Usage:
    python app.py [path/to/aws_inventory.json] [--port 8080]
"""

import argparse
import json
import os
import sys

from flask import Flask, jsonify, request, Response, send_from_directory

# Resolve paths relative to THIS script file, not the cwd
SCRIPT_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

from graph_builder import build_graph, get_filters, compute_stats

app = Flask(__name__)

INVENTORY = {}
GRAPH = {"nodes": [], "edges": []}
FILTERS = {"regions": [], "services": [], "types": []}
STATS = {}


def load_inventory(path):
    global INVENTORY, GRAPH, FILTERS, STATS
    with open(path) as f:
        INVENTORY = json.load(f)
    GRAPH = build_graph(INVENTORY)
    FILTERS = get_filters(GRAPH)
    STATS = compute_stats(INVENTORY)
    print(f"Loaded {len(GRAPH['nodes'])} nodes, {len(GRAPH['edges'])} edges")
    print(f"Regions: {FILTERS['regions']}")
    print(f"Services: {FILTERS['services']}")


# ── Serve static JS from script directory ────────────────────────────────
@app.route("/static/<path:filename>")
def serve_static(filename):
    static_dir = os.path.join(SCRIPT_DIR, "static")
    return send_from_directory(static_dir, filename)


# ── Serve index.html by reading the file directly (no Jinja) ────────────
@app.route("/")
def index():
    html_path = os.path.join(SCRIPT_DIR, "templates", "index.html")
    if not os.path.isfile(html_path):
        # Diagnostic info so you can see exactly what went wrong
        return Response(
            f"<pre>ERROR: index.html not found\n\n"
            f"Looked at:  {html_path}\n"
            f"SCRIPT_DIR: {SCRIPT_DIR}\n\n"
            f"Contents of SCRIPT_DIR:\n"
            f"  {chr(10).join(os.listdir(SCRIPT_DIR))}\n\n"
            f"templates/ dir exists: {os.path.isdir(os.path.join(SCRIPT_DIR, 'templates'))}\n"
            f"</pre>",
            status=500, content_type="text/html",
        )
    with open(html_path, "r", encoding="utf-8") as f:
        return Response(f.read(), content_type="text/html; charset=utf-8")


# ── API endpoints ────────────────────────────────────────────────────────
@app.route("/api/graph")
def api_graph():
    regions = request.args.get("regions", "")
    services = request.args.get("services", "")
    types = request.args.get("types", "")

    region_filter = set(regions.split(",")) if regions else None
    service_filter = set(services.split(",")) if services else None
    type_filter = set(types.split(",")) if types else None

    filtered_nodes = []
    node_ids = set()
    for n in GRAPH["nodes"]:
        if region_filter and n["region"] not in region_filter:
            continue
        if service_filter and n["service"] not in service_filter:
            continue
        if type_filter and n["type"] not in type_filter:
            continue
        filtered_nodes.append(n)
        node_ids.add(n["id"])

    filtered_edges = [
        e for e in GRAPH["edges"]
        if e["source"] in node_ids and e["target"] in node_ids
    ]

    return jsonify({"nodes": filtered_nodes, "edges": filtered_edges})


@app.route("/api/filters")
def api_filters():
    return jsonify(FILTERS)


@app.route("/api/stats")
def api_stats():
    return jsonify(STATS)


@app.route("/api/node/<path:node_id>")
def api_node_detail(node_id):
    for n in GRAPH["nodes"]:
        if n["id"] == node_id:
            connected = [
                e for e in GRAPH["edges"]
                if e["source"] == node_id or e["target"] == node_id
            ]
            return jsonify({"node": n, "edges": connected})
    return jsonify({"error": "not found"}), 404


# ── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", nargs="?", default=None,
                        help="Path to aws_inventory.json")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    inv_path = args.inventory
    if inv_path is None:
        inv_path = os.path.join(SCRIPT_DIR, "sample_inventory.json")

    if not os.path.exists(inv_path):
        print(f"Error: {inv_path} not found")
        sys.exit(1)

    # Diagnostics
    print(f"SCRIPT_DIR = {SCRIPT_DIR}")
    tpl = os.path.join(SCRIPT_DIR, "templates", "index.html")
    js  = os.path.join(SCRIPT_DIR, "static", "app.js")
    print(f"templates/index.html : {'OK' if os.path.isfile(tpl) else 'MISSING  (' + tpl + ')'}")
    print(f"static/app.js        : {'OK' if os.path.isfile(js) else 'MISSING  (' + js + ')'}")

    load_inventory(inv_path)
    print(f"\n🌐  http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
