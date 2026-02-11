# AWS Inventory Graph Visualizer

A web-based interactive graph ingestor and visualizer for AWS infrastructure data.

## Features

- **Interactive force-directed graph** — nodes represent AWS resources, edges represent relationships
- **VPC reachability visualization** — see which EC2 instances can reach each other through VPC configs, subnets, and security group rules
- **Security group flow** — dashed red edges show security-group-to-security-group ingress references (traffic flow paths)
- **Filter by region** — toggle regions on/off to focus on specific parts of your infrastructure
- **Filter by service** — isolate EC2, RDS, Lambda, S3, IAM, etc.
- **Search** — type to find nodes by name, ID, or type; press Enter to zoom to first match
- **Click to inspect** — right panel shows all metadata, properties, and connections for any node
- **Navigate connections** — click any connection in the detail panel to jump to that node
- **Neighbor highlighting** — clicking a node fades everything else and highlights its direct connections

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the ingestion tool first (if you haven't already)
python ingestor/aws_ingest.py --output aws_inventory.json

# 3. Start the visualizer
python visualizer/aws_visualizer.py aws_inventory.json

# 4. Open http://localhost:8080
```

## Usage

```bash
# Custom port
python aws_visualizer.py aws_inventory.json --port 9000

# Use the sample data (included for testing)
python aws_visualizer.py sample_inventory.json
```

## How to Read the Graph

| Node Shape   | Resource Type   |
| ------------ | --------------- |
| Rectangle    | VPC, Subnet     |
| Circle       | EC2 Instance    |
| Diamond      | Security Group  |
| Triangle     | Lambda Function |
| Hexagon      | Load Balancer   |
| Pentagon     | ECS/EKS Cluster |
| Barrel       | RDS Instance    |
| Star         | IAM User/Role   |
| Rounded Rect | S3 Bucket       |

| Edge Style     | Meaning                                           |
| -------------- | ------------------------------------------------- |
| Solid blue     | Network containment (VPC→Subnet→Instance)         |
| Solid yellow   | Security group membership                         |
| **Dashed red** | **Security group allows traffic from another SG** |
| Solid green    | Compute relationship (Cluster→Service)            |
| Solid purple   | Storage attachment                                |

### Understanding Reachability

Two EC2 instances **can reach each other** if:

1. They are in the **same VPC** (or VPCs connected via peering)
2. Their **security groups** allow the traffic — look for dashed red "allows-traffic-to" edges between their SGs

Instances in **different VPCs without peering** are isolated — you'll see them in separate graph clusters.
