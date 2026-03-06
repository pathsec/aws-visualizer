# AWS Inventory Graph Visualizer

A web-based interactive graph visualization for AWS infrastructure data collected by `aws_ingest.py`. Renders your entire AWS environment as an explorable network graph with contextual icons, color-coded resource types, and relationship edges showing VPC reachability, security group flows, and service dependencies.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.0%2B-green)
![Cytoscape.js](https://img.shields.io/badge/cytoscape.js-3.28-orange)

<p align="center">
  <img src="https://github.com/user-attachments/assets/3c5b79f6-d96e-47af-bbf8-b3118d308406" alt="Sample GUI screenshot" width="100%" />
</p>

<p align="center">
  <img src="https://github.com/user-attachments/assets/d670ea31-51b3-40c5-b559-1b925237f247" alt="Sample IAM analysis screenshot" width="100%" />
</p>


---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Ingest your AWS environment (if you haven't already)
python aws_ingest.py --output aws_inventory.json

# 3. Launch the visualizer
python aws_visualizer.py aws_inventory.json

# 4. Open http://localhost:8080
```

### Options

```bash
python aws_visualizer.py <inventory.json> [--port PORT] [--host HOST]

# Examples
python aws_visualizer.py aws_inventory.json --port 9000
python aws_visualizer.py sample_inventory.json              # use bundled sample data
python aws_visualizer.py                                     # defaults to sample_inventory.json
```

---

## Features

### Interactive Network Graph
- **Force-directed layout** positions related resources near each other automatically
- **Click any node** to inspect its full metadata and list of connections
- **Click connections** in the detail panel to navigate node-to-node through the graph
- **Neighbor highlighting** — clicking a node fades everything else and spotlights its direct relationships

### Filtering
- **By region** — toggle AWS regions on/off (left sidebar)
- **By service** — toggle EC2, RDS, Lambda, S3, IAM, etc. on/off
- Filters can be combined: e.g. show only `us-east-1` + `ec2` + `rds` to see just the networking + database topology for one region
- **All / None** buttons for quick bulk selection

### Search
- Type to find nodes by **name, ID, or type**
- Matching nodes are highlighted; non-matches are faded
- Press **Enter** to zoom to the first match
- Press **Escape** to clear

### Layout Modes
| Layout | Description |
|--------|-------------|
| **Force-directed** | Physics simulation; related nodes cluster together |
| **Hierarchical** | Tree from VPCs down through subnets to instances |
| **Grid** | Sorted grid grouped by service, then type |

---

## Node Icons

Every resource type has a contextual SVG icon rendered inside the node. Icons are white silhouettes on the resource's color background.

| Icon | Resource Type | Color |
|------|--------------|-------|
| ☁ Cloud | `vpc` | Blue `#3b82f6` |
| ⊞ Grid | `subnet` | Light blue `#60a5fa` |
| 🖥 Monitor | `ec2-instance` | Cyan `#22d3ee` |
| 🛡 Shield | `security-group` | Amber `#f59e0b` |
| 🌐 Globe | `internet-gateway` | Lime `#a3e635` |
| ➡ Arrow-box | `nat-gateway` | Green `#84cc16` |
| 📍 Pin | `elastic-ip` | Teal `#06b6d4` |
| 💾 Hard drive | `ebs-volume` | Purple `#8b5cf6` |
| 🔗 Link | `vpc-peering` | Lavender `#c084fc` |
| ⑂ Merge | `load-balancer` | Pink `#f472b6` |
| ⊕ Crosshair | `target-group` | Hot pink `#ec4899` |
| 🛢 Cylinder | `rds-instance` | Orange `#fb923c` |
| 🛢 Cylinder | `rds-cluster` | Deep orange `#f97316` |
| ⚡ Lightning | `lambda-function` | Yellow `#fbbf24` |
| ⬡ 3D box | `ecs-cluster` | Green `#4ade80` |
| ▶ Play | `ecs-service` | Emerald `#34d399` |
| ✱ Wheel | `eks-cluster` | Teal `#2dd4bf` |
| 🪣 Bucket | `s3-bucket` | Fuchsia `#e879f9` |
| 👤 Person | `iam-user` | Red `#f87171` |
| 👤+ Person-plus | `iam-role` | Light red `#fca5a5` |
| 📄 Document | `iam-policy` | Pale red `#fecaca` |
| 🗺 Map | `route53-zone` | Violet `#a78bfa` |
| T Type | `route53-record` | Light violet `#c4b5fd` |
| ✈ Send | `cloudfront` | Light cyan `#67e8f9` |
| ◇ Layers | `dynamodb-table` | Peach `#fdba74` |
| ☰ List | `sqs-queue` | Gold `#fcd34d` |
| 🔔 Bell | `sns-topic` | Mint `#86efac` |
| 🔒 Lock | `secret` | Rose `#fda4af` |
| 🔑 Key | `kms-key` | Light purple `#d8b4fe` |
| 📡 Tower | `api-gateway` | Pink-purple `#f0abfc` |
| 🏅 Badge | `acm-cert` | Ice blue `#a5f3fc` |
| 👁 Eye | `cloudtrail` | Lime `#bef264` |
| ◆ Stack | `cfn-stack` | Pale lime `#d9f99d` |
| ⬜ CPU | `elasticache-cluster` | Peach `#fdba74` |
| 📁 Folder | `efs` | Seafoam `#6ee7b7` |
| ⚠ Triangle | `error` | Red `#ef4444` |

---

## Edge Types & Colors

| Edge Style | Color | Meaning |
|-----------|-------|---------|
| Solid | Blue `#3b82f6` | **Network** — VPC → Subnet → Instance containment |
| Solid | Amber `#f59e0b` | **Security** — resource → security group membership |
| **Dashed** | **Red `#ef4444`** | **Security flow** — SG allows inbound from another SG |
| Solid | Green `#34d399` | **Compute** — Cluster → Service |
| Solid | Purple `#8b5cf6` | **Storage** — Instance → EBS volume |
| Solid | Violet `#a78bfa` | **DNS** — Route53 zone/record relationships |
| Solid | Cyan `#67e8f9` | **CDN** — CloudFront → S3 origin |
| Solid | Red `#f87171` | **IAM** — Lambda/User → Role/Policy |
| Solid | Lime `#bef264` | **Logging** — CloudTrail → S3 bucket |
| Solid | Gray `#576577` | **Other** — generic relationships |

---

## Understanding Reachability

Two resources **can reach each other** if:

1. They are in the **same VPC** (or connected VPCs via a peering node)
2. Their **security groups** allow the traffic — look for dashed red `allows-traffic-to` edges between their SGs

**Example flow visible in the sample data:**

```
web-sg ──allows-traffic-to──▶ app-sg ──allows-traffic-to──▶ rds-sg
   │                             │                             │
web-server-1               app-server-1                   prod-postgres
web-server-2
bastion-host
```

This shows: web servers can reach the app tier on port 8080, the app tier can reach Postgres on 5432, but the web tier **cannot** directly reach the database.

Instances in **different VPCs without peering** appear as separate graph clusters — visually isolated.

---

## IAM Attack Path Analysis

The visualizer integrates with [**pathfinding.cloud**](https://pathfinding.cloud) — a catalogue of IAM privilege escalation paths originally built by [DataDog Security Research](https://github.com/DataDog/pathfinding.cloud). Full credit and thanks to the DataDog team for publishing this research.

### How it works

Enable the **IAM Attack Paths** toggle in the left sidebar (on by default). Type in the search box to find an IAM user or role, or simply click any IAM node in the graph to auto-select it.

The analyser extracts the principal's effective permissions by reading:
- Inline policies attached directly to the user or role
- Customer-managed policies (with their full policy documents)
- Well-known AWS managed policies (by ARN)

It then matches those permissions against every escalation path from `pathfinding.cloud/paths.json` and displays:

| Result | Meaning |
|--------|---------|
| **Fully applicable** | The principal holds **every** required permission for this path |
| **Partial match** | At least one required permission is granted — shows which are missing |

Click any path chip for full details: description, exploitation steps, prerequisites, limitations, and detection tools.

### Path categories

| Badge | Category | Description |
|-------|----------|-------------|
| 🔴 | `self-escalation` | Principal can escalate their own permissions |
| 🟠 | `principal-access` | Principal can gain access to another principal |
| 🟣 | `new-passrole` | PassRole to a newly created resource |
| 🟣 | `existing-passrole` | PassRole to an existing resource |
| 🩷 | `credential-access` | Credential theft without privilege escalation |

### Required IAM data

For accurate analysis, the ingestor (`aws_ingest.py`) collects:
- Role attached and inline policies (`list_attached_role_policies`, `list_role_policies`, `get_role_policy`)
- User inline policies (`list_user_policies`, `get_user_policy`)
- Customer-managed policy documents (`get_policy_version` using `DefaultVersionId`)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Stuck on "Building graph…" | Open F12 console — check if Cytoscape.js CDN is blocked. Download `cytoscape.min.js` into `static/` and update the `<script>` src in `index.html` |
| Empty graph | Check that your inventory JSON has data in `regional_services`. Try the sample: `python aws_visualizer.py sample_inventory.json` |
| Slow with large inventories | Reduce regions with filters, or run with `--regions us-east-1` in the ingestion tool |
