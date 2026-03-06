#!/usr/bin/env python3
"""
AWS Visualizer
========================================
Usage:
    python app.py [path/to/aws_inventory.json ...] [--port 8080]

Supports loading multiple inventory files at startup via CLI,
and importing/clearing data at runtime via the web UI.
"""

import argparse
import json
import os
import sys
import datetime
import urllib.request
from collections import defaultdict

from flask import Flask, jsonify, request, Response, send_from_directory

SCRIPT_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

from graph_builder import build_graph, get_filters, compute_stats

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload

# ── State ─────────────────────────────────────────────────────────────────
SOURCES = []          # list of {"name": str, "inventory": dict, "loaded_at": str}
GRAPH = {"nodes": [], "edges": []}
FILTERS = {"regions": [], "services": [], "types": []}
STATS = {}
# Pre-built indexes for fast filtering
_NODE_BY_REGION = {}   # region -> [node, ...]
_NODE_BY_SERVICE = {}  # service -> [node, ...]
_EDGE_INDEX = {}       # source_id -> [edge, ...], target_id -> [edge, ...]


def _merge_inventories():
    """Merge all loaded inventory sources into one combined inventory, then rebuild the graph."""
    global GRAPH, FILTERS, STATS

    if not SOURCES:
        GRAPH = {"nodes": [], "edges": []}
        FILTERS = {"regions": [], "services": [], "types": []}
        STATS = {"ingestion_time": "—", "regions_scanned": 0, "regions_active": 0,
                 "s3_buckets": 0, "iam_users": 0, "iam_roles": 0, "ec2_instances": 0,
                 "vpcs": 0, "lambda_functions": 0, "rds_instances": 0, "total_errors": 0}
        _NODE_BY_REGION.clear()
        _NODE_BY_SERVICE.clear()
        _EDGE_INDEX.clear()
        return

    # Start with an empty combined inventory
    combined = {
        "metadata": {
            "ingestion_time": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            "regions_scanned": [],
            "profile": "merged",
            "summary": {},
        },
        "global_services": {},
        "regional_services": {},
        "errors": {"global": [], "regional": {}},
    }

    all_regions = set()
    for src in SOURCES:
        inv = src["inventory"]
        meta = inv.get("metadata", {})
        all_regions.update(meta.get("regions_scanned", []))

        # Merge global services
        for svc_name, svc_data in inv.get("global_services", {}).items():
            if svc_name not in combined["global_services"]:
                combined["global_services"][svc_name] = svc_data
            else:
                # Merge lists within global services
                existing = combined["global_services"][svc_name]
                for key, val in svc_data.items():
                    if isinstance(val, list) and isinstance(existing.get(key), list):
                        # Dedupe by checking if items are already present (simple approach)
                        existing_set = {json.dumps(v, sort_keys=True, default=str) for v in existing[key]}
                        for item in val:
                            if json.dumps(item, sort_keys=True, default=str) not in existing_set:
                                existing[key].append(item)
                    elif key not in existing:
                        existing[key] = val

        # Merge regional services
        for region, services in inv.get("regional_services", {}).items():
            if region not in combined["regional_services"]:
                combined["regional_services"][region] = services
            else:
                existing_region = combined["regional_services"][region]
                for svc_name, svc_data in services.items():
                    if svc_name not in existing_region:
                        existing_region[svc_name] = svc_data
                    else:
                        # Merge lists within services
                        existing_svc = existing_region[svc_name]
                        for key, val in svc_data.items():
                            if isinstance(val, list) and isinstance(existing_svc.get(key), list):
                                existing_set = {json.dumps(v, sort_keys=True, default=str) for v in existing_svc[key]}
                                for item in val:
                                    if json.dumps(item, sort_keys=True, default=str) not in existing_set:
                                        existing_svc[key].append(item)
                            elif key not in existing_svc:
                                existing_svc[key] = val

        # Merge errors
        combined["errors"]["global"].extend(inv.get("errors", {}).get("global", []))
        for region, errs in inv.get("errors", {}).get("regional", {}).items():
            if region not in combined["errors"]["regional"]:
                combined["errors"]["regional"][region] = []
            combined["errors"]["regional"][region].extend(errs)

    combined["metadata"]["regions_scanned"] = sorted(all_regions)

    GRAPH = build_graph(combined)
    FILTERS = get_filters(GRAPH)
    STATS = compute_stats(combined)
    _rebuild_indexes()
    print(f"[merge] {len(SOURCES)} source(s) → {len(GRAPH['nodes'])} nodes, {len(GRAPH['edges'])} edges")


def _rebuild_indexes():
    """Build lookup indexes for fast filtering."""
    global _NODE_BY_REGION, _NODE_BY_SERVICE, _EDGE_INDEX
    _NODE_BY_REGION = defaultdict(list)
    _NODE_BY_SERVICE = defaultdict(list)
    _EDGE_INDEX = defaultdict(list)
    for n in GRAPH["nodes"]:
        _NODE_BY_REGION[n["region"]].append(n)
        _NODE_BY_SERVICE[n["service"]].append(n)
    for e in GRAPH["edges"]:
        _EDGE_INDEX[e["source"]].append(e)
        _EDGE_INDEX[e["target"]].append(e)


def load_inventory_file(path):
    """Load an inventory file from disk and add it as a source."""
    with open(path) as f:
        inv = json.load(f)
    name = os.path.basename(path)
    SOURCES.append({
        "name": name,
        "loaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        "inventory": inv,
    })
    _merge_inventories()


# ── Static / HTML ─────────────────────────────────────────────────────────
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(SCRIPT_DIR, "static"), filename)


@app.route("/")
def index():
    html_path = os.path.join(SCRIPT_DIR, "templates", "index.html")
    if not os.path.isfile(html_path):
        return Response(f"<pre>index.html not found at {html_path}</pre>", 500, content_type="text/html")
    with open(html_path, "r", encoding="utf-8") as f:
        return Response(f.read(), content_type="text/html; charset=utf-8")


# ── Data management API ───────────────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload one or more inventory JSON files."""
    if "file" not in request.files:
        return jsonify({"error": "no file field"}), 400

    files = request.files.getlist("file")
    added = []
    for f in files:
        if not f.filename:
            continue
        try:
            inv = json.load(f)
            SOURCES.append({
                "name": f.filename,
                "loaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                "inventory": inv,
            })
            added.append(f.filename)
        except Exception as e:
            return jsonify({"error": f"Failed to parse {f.filename}: {str(e)}"}), 400

    _merge_inventories()
    return jsonify({"added": added, "total_sources": len(SOURCES),
                    "nodes": len(GRAPH["nodes"]), "edges": len(GRAPH["edges"])})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """Clear all loaded data."""
    SOURCES.clear()
    _merge_inventories()
    return jsonify({"status": "cleared", "total_sources": 0, "nodes": 0, "edges": 0})


@app.route("/api/remove_source", methods=["POST"])
def api_remove_source():
    """Remove a single source by index."""
    data = request.get_json(silent=True) or {}
    idx = data.get("index")
    if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(SOURCES):
        return jsonify({"error": "invalid index"}), 400
    removed = SOURCES.pop(idx)
    _merge_inventories()
    return jsonify({"removed": removed["name"], "total_sources": len(SOURCES),
                    "nodes": len(GRAPH["nodes"]), "edges": len(GRAPH["edges"])})


@app.route("/api/sources")
def api_sources():
    """List loaded data sources."""
    return jsonify([{"name": s["name"], "loaded_at": s["loaded_at"]} for s in SOURCES])


# ── Graph API ─────────────────────────────────────────────────────────────
@app.route("/api/graph")
def api_graph():
    regions = request.args.get("regions", "")
    services = request.args.get("services", "")

    if regions == "_none_" or services == "_none_":
        return jsonify({"nodes": [], "edges": []})

    region_filter = set(regions.split(",")) if regions else None
    service_filter = set(services.split(",")) if services else None

    # Use indexes for fast filtering
    if region_filter and service_filter:
        # Intersect: get nodes matching both filters
        region_nodes = set()
        for r in region_filter:
            for n in _NODE_BY_REGION.get(r, []):
                region_nodes.add(n["id"])
        node_ids = set()
        filtered_nodes = []
        for s in service_filter:
            for n in _NODE_BY_SERVICE.get(s, []):
                if n["id"] in region_nodes and n["id"] not in node_ids:
                    filtered_nodes.append(n)
                    node_ids.add(n["id"])
    elif region_filter:
        node_ids = set()
        filtered_nodes = []
        for r in region_filter:
            for n in _NODE_BY_REGION.get(r, []):
                if n["id"] not in node_ids:
                    filtered_nodes.append(n)
                    node_ids.add(n["id"])
    elif service_filter:
        node_ids = set()
        filtered_nodes = []
        for s in service_filter:
            for n in _NODE_BY_SERVICE.get(s, []):
                if n["id"] not in node_ids:
                    filtered_nodes.append(n)
                    node_ids.add(n["id"])
    else:
        filtered_nodes = GRAPH["nodes"]
        node_ids = {n["id"] for n in filtered_nodes}

    # Filter edges using index
    seen_edges = set()
    filtered_edges = []
    for nid in node_ids:
        for e in _EDGE_INDEX.get(nid, []):
            eid = id(e)
            if eid not in seen_edges and e["source"] in node_ids and e["target"] in node_ids:
                filtered_edges.append(e)
                seen_edges.add(eid)

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
            connected = [e for e in GRAPH["edges"]
                         if e["source"] == node_id or e["target"] == node_id]
            return jsonify({"node": n, "edges": connected})
    return jsonify({"error": "not found"}), 404


# ── IAM Attack Path Analysis ──────────────────────────────────────────────
# Permissions granted by well-known AWS managed policies (simplified but covers common escalation vectors)
_WELL_KNOWN_MANAGED_POLICIES = {
    "arn:aws:iam::aws:policy/AdministratorAccess": ["*"],
    "arn:aws:iam::aws:policy/PowerUserAccess": ["*"],
    "arn:aws:iam::aws:policy/IAMFullAccess": ["iam:*"],
    "arn:aws:iam::aws:policy/IAMReadOnlyAccess": [
        "iam:Get*", "iam:List*", "iam:Generate*"],
    "arn:aws:iam::aws:policy/AmazonEC2FullAccess": ["ec2:*", "elasticloadbalancing:*",
        "cloudwatch:*", "autoscaling:*"],
    "arn:aws:iam::aws:policy/AWSLambdaFullAccess": ["lambda:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/AWSLambda_FullAccess": ["lambda:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/AmazonS3FullAccess": ["s3:*"],
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess": ["dynamodb:*"],
    "arn:aws:iam::aws:policy/AmazonECS_FullAccess": ["ecs:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy": ["ec2:*", "elasticloadbalancing:*",
        "autoscaling:*", "cloudwatch:*"],
    "arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess": ["codebuild:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/AWSCodePipelineFullAccess": ["codepipeline:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/AWSGlueServiceRole": ["glue:*", "s3:*", "ec2:*", "cloudwatch:*"],
    "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess": ["sagemaker:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/AWSDataPipelineFullAccess": ["datapipeline:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/AmazonRDSFullAccess": ["rds:*"],
    "arn:aws:iam::aws:policy/CloudWatchFullAccess": ["cloudwatch:*", "logs:*"],
    "arn:aws:iam::aws:policy/AWSCloudFormationFullAccess": ["cloudformation:*", "iam:PassRole"],
    "arn:aws:iam::aws:policy/SecurityAudit": [
        "acm:List*", "acm:Describe*", "cloudtrail:Get*", "cloudtrail:Describe*",
        "cloudtrail:List*", "ec2:Describe*", "iam:Get*", "iam:List*",
        "s3:GetBucketAcl", "s3:GetBucketPolicy", "s3:ListAllMyBuckets"],
    "arn:aws:iam::aws:policy/ReadOnlyAccess": [
        "ec2:Describe*", "s3:Get*", "s3:List*", "iam:Get*", "iam:List*",
        "lambda:Get*", "lambda:List*", "rds:Describe*", "cloudwatch:Get*",
        "cloudwatch:List*", "cloudwatch:Describe*"],
}

_PATHFINDING_PATHS = []
_PATHFINDING_LOADED = False


def _load_pathfinding_paths():
    """Fetch and cache pathfinding.cloud paths at first call."""
    global _PATHFINDING_PATHS, _PATHFINDING_LOADED
    if _PATHFINDING_LOADED:
        return _PATHFINDING_PATHS
    try:
        url = "https://pathfinding.cloud/paths.json"
        req = urllib.request.Request(url, headers={"User-Agent": "aws-visualizer/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            _PATHFINDING_PATHS = json.loads(resp.read().decode())
        print(f"[iam] Loaded {len(_PATHFINDING_PATHS)} pathfinding.cloud paths")
    except Exception as e:
        print(f"[iam] Could not load pathfinding.cloud paths: {e}")
        _PATHFINDING_PATHS = []
    _PATHFINDING_LOADED = True
    return _PATHFINDING_PATHS


def _get_all_iam_data():
    """Return the IAM section from the first source that has it."""
    for src in SOURCES:
        iam_data = src["inventory"].get("global_services", {}).get("iam", {})
        if iam_data:
            return iam_data
    return {}


def _parse_policy_document(doc):
    """Extract all Allow action strings (lowercased) from a policy document."""
    if not doc:
        return set()
    perms = set()
    statements = doc.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    for stmt in statements:
        if stmt.get("Effect", "") != "Allow":
            continue
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        perms.update(a.lower() for a in actions)
    return perms


def _permission_covers(granted_lower, required_lower):
    """Return True if a granted permission string covers the required permission."""
    if granted_lower == "*":
        return True
    if granted_lower == required_lower:
        return True
    # Service-level wildcard: "iam:*" covers "iam:passrole"
    if granted_lower.endswith(":*"):
        service = granted_lower[:-2]
        if required_lower.startswith(service + ":"):
            return True
    # Prefix wildcard used in ReadOnly policies: "iam:list*" covers "iam:listpolicies"
    if "*" in granted_lower:
        prefix = granted_lower.split("*")[0]
        if required_lower.startswith(prefix):
            return True
    return False


def _get_principal_permissions(node_id):
    """Return the set of lowercased effective permissions for an IAM user or role node."""
    iam_data = _get_all_iam_data()
    perms = set()
    policy_map = {p["Arn"]: p for p in iam_data.get("policies", [])}

    def _apply_managed_policy(parn):
        if parn in _WELL_KNOWN_MANAGED_POLICIES:
            perms.update(a.lower() for a in _WELL_KNOWN_MANAGED_POLICIES[parn])
        elif parn in policy_map:
            perms.update(_parse_policy_document(policy_map[parn].get("document", {})))

    if node_id.startswith("iam-user:"):
        uid = node_id[9:]
        user = next((u for u in iam_data.get("users", []) if u.get("UserId") == uid), None)
        if user:
            for ip in user.get("inline_policies", []):
                perms.update(_parse_policy_document(ip.get("PolicyDocument", {})))
            for ap in user.get("attached_policies", []):
                _apply_managed_policy(ap.get("PolicyArn", ""))

    elif node_id.startswith("iam-role:"):
        rid = node_id[9:]
        role = next((r for r in iam_data.get("roles", []) if r.get("RoleId") == rid), None)
        if role:
            for ip in role.get("inline_policies", []):
                perms.update(_parse_policy_document(ip.get("PolicyDocument", {})))
            for ap in role.get("attached_policies", []):
                _apply_managed_policy(ap.get("PolicyArn", ""))

    return perms


def _evaluate_path(path, perms):
    """
    Evaluate a pathfinding.cloud path against a set of permissions.
    Returns dict with matched, missing, fully_applicable.
    """
    required = path.get("permissions", {}).get("required", [])
    if not required:
        return None  # skip paths with no requirements defined

    matched = []
    missing = []
    for req in required:
        perm_str = req.get("permission", "")
        perm_lower = perm_str.lower()
        found = any(_permission_covers(p, perm_lower) for p in perms)
        if found:
            matched.append(perm_str)
        else:
            missing.append(perm_str)

    if not matched:
        return None  # no overlap at all, skip

    return {
        "id": path.get("id"),
        "name": path.get("name"),
        "category": path.get("category"),
        "services": path.get("services", []),
        "description": path.get("description", ""),
        "exploitationSteps": path.get("exploitationSteps", ""),
        "prerequisites": path.get("prerequisites", ""),
        "limitations": path.get("limitations", ""),
        "detectionTools": path.get("detectionTools", []),
        "matched_permissions": matched,
        "missing_permissions": missing,
        "fully_applicable": len(missing) == 0,
    }


@app.route("/api/iam_principals")
def api_iam_principals():
    """Return all IAM user and role nodes from the current graph."""
    principals = [
        {"id": n["id"], "label": n.get("label", n["id"]), "type": n.get("type", ""),
         "service": n.get("service", ""), "region": n.get("region", "")}
        for n in GRAPH["nodes"]
        if n.get("type") in ("iam-user", "iam-role")
    ]
    return jsonify(principals)


@app.route("/api/pathfinding_paths")
def api_pathfinding_paths():
    """Return the full cached list from pathfinding.cloud."""
    paths = _load_pathfinding_paths()
    return jsonify(paths)


@app.route("/api/iam_attack_paths")
def api_iam_attack_paths():
    """
    Evaluate IAM privilege escalation paths for a given principal.
    Query param: source=<node_id>
    Returns applicable and partially-applicable paths.
    """
    source = request.args.get("source", "")
    if not source:
        return jsonify({"error": "source param required"}), 400
    if not source.startswith(("iam-user:", "iam-role:")):
        return jsonify({"error": "source must be an iam-user or iam-role node id"}), 400

    paths = _load_pathfinding_paths()
    perms = _get_principal_permissions(source)

    results = []
    for path in paths:
        evaluated = _evaluate_path(path, perms)
        if evaluated:
            results.append(evaluated)

    # Sort: fully applicable first, then by number of matched perms descending
    results.sort(key=lambda r: (not r["fully_applicable"], -len(r["matched_permissions"])))

    return jsonify({
        "source": source,
        "permissions_count": len(perms),
        "paths": results,
        "fully_applicable": sum(1 for r in results if r["fully_applicable"]),
        "partially_applicable": sum(1 for r in results if not r["fully_applicable"]),
    })


# ── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", nargs="*", default=[],
                        help="Path(s) to aws_inventory.json file(s)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"SCRIPT_DIR = {SCRIPT_DIR}")

    # Load any CLI-provided inventory files
    for inv_path in args.inventory:
        if os.path.exists(inv_path):
            print(f"Loading: {inv_path}")
            load_inventory_file(inv_path)
        else:
            print(f"Warning: {inv_path} not found, skipping")

    if not SOURCES:
        # Try default sample
        sample = os.path.join(SCRIPT_DIR, "sample_inventory.json")
        if os.path.exists(sample):
            print(f"No files specified, loading sample: {sample}")
            load_inventory_file(sample)
        else:
            print("No inventory loaded. Use the web UI to import data.")

    print(f"\n🌐  http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
