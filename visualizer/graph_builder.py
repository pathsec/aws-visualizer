"""
graph_builder.py – Transforms an AWS inventory JSON into a graph of nodes + edges.

Each node has:
    id, label, type (service kind), region, service, metadata (extra info)

Each edge has:
    source, target, label, type (relationship kind)
"""

import json
from collections import defaultdict


def get_name_tag(tags):
    """Extract the Name tag from a list of {Key, Value} dicts."""
    if not tags:
        return None
    if isinstance(tags, list):
        for t in tags:
            if t.get("Key") == "Name":
                return t["Value"]
    return None


def build_graph(inventory: dict) -> dict:
    """
    Parse the full inventory dict and return:
        {"nodes": [...], "edges": [...]}
    """
    nodes = []
    edges = []
    seen_ids = set()

    def add_node(nid, label, ntype, region, service, metadata=None):
        if nid in seen_ids:
            return
        seen_ids.add(nid)
        nodes.append({
            "id": nid,
            "label": label,
            "type": ntype,
            "region": region or "global",
            "service": service,
            "metadata": metadata or {},
        })

    def add_edge(src, tgt, label, etype="relationship"):
        edges.append({"source": src, "target": tgt, "label": label, "type": etype})

    # ----- helpers to track cross-references -----
    sg_to_vpc = {}      # sg-xxx -> vpc-xxx
    subnet_to_vpc = {}  # subnet-xxx -> vpc-xxx
    instance_sgs = {}   # i-xxx -> [sg-xxx, ...]
    sg_inbound_refs = defaultdict(list)  # sg-xxx -> [sg-yyy, ...] meaning sg-yyy allows traffic from sg-xxx

    # =========================================================================
    # GLOBAL SERVICES
    # =========================================================================
    gs = inventory.get("global_services", {})

    # --- IAM ---
    iam = gs.get("iam", {})
    for u in iam.get("users", []):
        uid = u.get("UserId", u.get("UserName"))
        uname = u.get("UserName", uid)
        add_node(f"iam-user:{uid}", uname, "iam-user", "global", "iam", {
            "arn": u.get("Arn"),
            "mfa_enabled": len(u.get("mfa_devices", [])) > 0,
            "active_keys": sum(1 for k in u.get("access_keys", []) if k.get("Status") == "Active"),
        })
        for pol in u.get("attached_policies", []):
            pid = pol.get("PolicyArn", pol.get("PolicyName"))
            pname = pol.get("PolicyName", pid)
            add_node(f"iam-policy:{pid}", pname, "iam-policy", "global", "iam")
            add_edge(f"iam-user:{uid}", f"iam-policy:{pid}", "attached", "iam")

    for r in iam.get("roles", []):
        rid = r.get("RoleId", r.get("RoleName"))
        rname = r.get("RoleName", rid)
        add_node(f"iam-role:{rid}", rname, "iam-role", "global", "iam", {"arn": r.get("Arn")})

    # --- S3 ---
    s3 = gs.get("s3", {})
    for b in s3.get("buckets", []):
        bname = b["Name"]
        enc = "none"
        enc_cfg = b.get("encryption", {})
        if isinstance(enc_cfg, dict):
            rules = enc_cfg.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
            if rules:
                enc = rules[0].get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm", "unknown")
        add_node(f"s3:{bname}", bname, "s3-bucket", "global", "s3", {
            "encryption": enc,
            "tags": b.get("tagging", []),
        })

    # --- Route53 ---
    r53 = gs.get("route53", {})
    for z in r53.get("hosted_zones", []):
        zid = z["Id"].split("/")[-1]
        zname = z.get("Name", zid)
        add_node(f"r53:{zid}", zname, "route53-zone", "global", "route53")
        for rs in z.get("record_sets", []):
            rname = rs.get("Name", "")
            rtype = rs.get("Type", "")
            rid = f"r53-rec:{zid}:{rname}:{rtype}"
            add_node(rid, f"{rname} ({rtype})", "route53-record", "global", "route53", {
                "type": rtype,
            })
            add_edge(f"r53:{zid}", rid, "contains", "dns")
            # Try to link alias targets
            alias = rs.get("AliasTarget", {})
            if alias:
                dns_name = alias.get("DNSName", "")
                # Try to match CloudFront
                if "cloudfront.net" in dns_name:
                    for d in gs.get("cloudfront", {}).get("distributions", []):
                        if d.get("DomainName") and dns_name.rstrip(".").endswith(d["DomainName"].rstrip(".")):
                            add_edge(rid, f"cf:{d['Id']}", "alias-to", "dns")
                # Try to match ELB
                if "elb.amazonaws.com" in dns_name:
                    # defer to regional pass
                    pass

    # --- CloudFront ---
    cf = gs.get("cloudfront", {})
    for d in cf.get("distributions", []):
        did = d.get("Id")
        dname = d.get("DomainName", did)
        add_node(f"cf:{did}", dname, "cloudfront", "global", "cloudfront", {
            "status": d.get("Status"),
        })
        origins = d.get("Origins", {}).get("Items", [])
        for o in origins:
            odom = o.get("DomainName", "")
            if ".s3." in odom or odom.endswith(".s3.amazonaws.com"):
                bucket_name = odom.split(".s3")[0]
                if f"s3:{bucket_name}" in seen_ids:
                    add_edge(f"cf:{did}", f"s3:{bucket_name}", "origin", "cdn")

    # =========================================================================
    # REGIONAL SERVICES
    # =========================================================================
    for region, services in inventory.get("regional_services", {}).items():
        # --- EC2 ---
        ec2 = services.get("ec2", {})

        # VPCs
        for v in ec2.get("vpcs", []):
            vid = v["VpcId"]
            vname = get_name_tag(v.get("Tags")) or vid
            add_node(f"vpc:{vid}", f"{vname} ({v.get('CidrBlock', '')})", "vpc", region, "ec2", {
                "cidr": v.get("CidrBlock"),
                "state": v.get("State"),
            })

        # Subnets
        for s in ec2.get("subnets", []):
            sid = s["SubnetId"]
            sname = get_name_tag(s.get("Tags")) or sid
            vpc_id = s.get("VpcId")
            subnet_to_vpc[sid] = vpc_id
            add_node(f"subnet:{sid}", f"{sname} ({s.get('CidrBlock', '')})", "subnet", region, "ec2", {
                "az": s.get("AvailabilityZone"),
                "cidr": s.get("CidrBlock"),
                "public": s.get("MapPublicIpOnLaunch", False),
            })
            if vpc_id:
                add_edge(f"vpc:{vpc_id}", f"subnet:{sid}", "contains", "network")

        # Security Groups
        for sg in ec2.get("security_groups", []):
            sgid = sg["GroupId"]
            sgname = sg.get("GroupName", sgid)
            vpc_id = sg.get("VpcId")
            sg_to_vpc[sgid] = vpc_id
            rules_summary = []
            for rule in sg.get("IpPermissions", []):
                proto = rule.get("IpProtocol", "")
                fp = rule.get("FromPort", "")
                tp = rule.get("ToPort", "")
                port_str = f"{fp}" if fp == tp else f"{fp}-{tp}"
                if proto == "-1":
                    port_str = "all"
                    proto = "all"
                for cidr in rule.get("IpRanges", []):
                    rules_summary.append(f"{proto}:{port_str} from {cidr.get('CidrIp')}")
                for pair in rule.get("UserIdGroupPairs", []):
                    ref_sg = pair.get("GroupId")
                    rules_summary.append(f"{proto}:{port_str} from {ref_sg}")
                    if ref_sg:
                        sg_inbound_refs[sgid].append(ref_sg)

            add_node(f"sg:{sgid}", sgname, "security-group", region, "ec2", {
                "vpc": vpc_id,
                "rules": rules_summary,
            })
            if vpc_id:
                add_edge(f"vpc:{vpc_id}", f"sg:{sgid}", "contains", "network")

        # IGWs
        for igw in ec2.get("internet_gateways", []):
            igw_id = igw["InternetGatewayId"]
            igw_name = get_name_tag(igw.get("Tags")) or igw_id
            add_node(f"igw:{igw_id}", igw_name, "internet-gateway", region, "ec2")
            for att in igw.get("Attachments", []):
                vid = att.get("VpcId")
                if vid:
                    add_edge(f"vpc:{vid}", f"igw:{igw_id}", "attached", "network")

        # NAT Gateways
        for nat in ec2.get("nat_gateways", []):
            nat_id = nat["NatGatewayId"]
            nat_name = get_name_tag(nat.get("Tags")) or nat_id
            add_node(f"nat:{nat_id}", nat_name, "nat-gateway", region, "ec2", {
                "state": nat.get("State"),
            })
            sid = nat.get("SubnetId")
            if sid:
                add_edge(f"subnet:{sid}", f"nat:{nat_id}", "hosts", "network")
            vid = nat.get("VpcId")
            if vid:
                add_edge(f"vpc:{vid}", f"nat:{nat_id}", "contains", "network")

        # EC2 Instances
        for res in ec2.get("instances", []):
            for inst in res.get("Instances", []):
                iid = inst["InstanceId"]
                iname = get_name_tag(inst.get("Tags")) or iid
                state = inst.get("State", {}).get("Name", "unknown")
                vpc_id = inst.get("VpcId")
                subnet_id = inst.get("SubnetId")
                sgs = [sg["GroupId"] for sg in inst.get("SecurityGroups", [])]
                instance_sgs[iid] = sgs

                add_node(f"ec2:{iid}", iname, "ec2-instance", region, "ec2", {
                    "instance_type": inst.get("InstanceType"),
                    "state": state,
                    "private_ip": inst.get("PrivateIpAddress"),
                    "public_ip": inst.get("PublicIpAddress"),
                    "vpc": vpc_id,
                    "subnet": subnet_id,
                })

                if subnet_id:
                    add_edge(f"subnet:{subnet_id}", f"ec2:{iid}", "hosts", "network")
                for sg in sgs:
                    add_edge(f"ec2:{iid}", f"sg:{sg}", "member-of", "security")

        # VPC Peering
        for pc in ec2.get("vpc_peering_connections", []):
            pcid = pc["VpcPeeringConnectionId"]
            status = pc.get("Status", {}).get("Code", "unknown")
            req_vpc = pc.get("RequesterVpcInfo", {}).get("VpcId")
            acc_vpc = pc.get("AccepterVpcInfo", {}).get("VpcId")
            add_node(f"pcx:{pcid}", pcid, "vpc-peering", region, "ec2", {"status": status})
            if req_vpc:
                add_edge(f"vpc:{req_vpc}", f"pcx:{pcid}", "requester", "network")
            if acc_vpc:
                add_edge(f"vpc:{acc_vpc}", f"pcx:{pcid}", "accepter", "network")

        # EIPs
        for eip in ec2.get("elastic_ips", []):
            eip_id = eip.get("AllocationId", eip.get("PublicIp"))
            add_node(f"eip:{eip_id}", eip.get("PublicIp", eip_id), "elastic-ip", region, "ec2")
            iid = eip.get("InstanceId")
            if iid:
                add_edge(f"eip:{eip_id}", f"ec2:{iid}", "associated", "network")

        # Volumes
        for vol in ec2.get("volumes", []):
            volid = vol["VolumeId"]
            volname = get_name_tag(vol.get("Tags")) or volid
            add_node(f"ebs:{volid}", f"{volname} ({vol.get('Size', '?')}GB)", "ebs-volume", region, "ec2", {
                "size_gb": vol.get("Size"),
                "state": vol.get("State"),
            })
            for att in vol.get("Attachments", []):
                iid = att.get("InstanceId")
                if iid:
                    add_edge(f"ec2:{iid}", f"ebs:{volid}", "attached", "storage")

        # --- RDS ---
        rds = services.get("rds", {})
        for db in rds.get("db_instances", []):
            dbid = db["DBInstanceIdentifier"]
            dbname = get_name_tag(db.get("Tags")) or dbid
            endpoint = db.get("Endpoint", {})
            vpc_id = db.get("DBSubnetGroup", {}).get("VpcId")
            sgs = [sg["VpcSecurityGroupId"] for sg in db.get("VpcSecurityGroups", [])]
            add_node(f"rds:{dbid}", dbname, "rds-instance", region, "rds", {
                "engine": db.get("Engine"),
                "class": db.get("DBInstanceClass"),
                "status": db.get("DBInstanceStatus"),
                "endpoint": endpoint.get("Address"),
                "port": endpoint.get("Port"),
                "multi_az": db.get("MultiAZ"),
                "encrypted": db.get("StorageEncrypted"),
            })
            if vpc_id:
                add_edge(f"vpc:{vpc_id}", f"rds:{dbid}", "hosts", "network")
            for sg in sgs:
                add_edge(f"rds:{dbid}", f"sg:{sg}", "member-of", "security")

        for cl in rds.get("db_clusters", []):
            clid = cl.get("DBClusterIdentifier", "")
            clname = get_name_tag(cl.get("Tags")) or clid
            add_node(f"rds-cluster:{clid}", clname, "rds-cluster", region, "rds", {
                "engine": cl.get("Engine"),
                "status": cl.get("Status"),
            })

        # --- Lambda ---
        lam = services.get("lambda", {})
        for fn in lam.get("functions", []):
            fname = fn["FunctionName"]
            vpc_cfg = fn.get("VpcConfig", {})
            vpc_id = vpc_cfg.get("VpcId")
            lam_sgs = vpc_cfg.get("SecurityGroupIds", [])
            lam_subnets = vpc_cfg.get("SubnetIds", [])
            role_arn = fn.get("Role", "")
            add_node(f"lambda:{fname}", fname, "lambda-function", region, "lambda", {
                "runtime": fn.get("Runtime"),
                "vpc": vpc_id,
                "memory": fn.get("MemorySize"),
            })
            if vpc_id:
                for sid in lam_subnets:
                    add_edge(f"subnet:{sid}", f"lambda:{fname}", "hosts", "network")
                for sg in lam_sgs:
                    add_edge(f"lambda:{fname}", f"sg:{sg}", "member-of", "security")
            # Link to IAM role
            for r in iam.get("roles", []):
                if r.get("Arn") == role_arn:
                    rid = r.get("RoleId", r.get("RoleName"))
                    add_edge(f"lambda:{fname}", f"iam-role:{rid}", "assumes", "iam")

        # --- ECS ---
        ecs = services.get("ecs", {})
        for cl in ecs.get("clusters", []):
            cname = cl.get("clusterName", "")
            carn = cl.get("clusterArn", "")
            add_node(f"ecs-cluster:{cname}", cname, "ecs-cluster", region, "ecs", {
                "status": cl.get("status"),
                "running_tasks": cl.get("runningTasksCount"),
            })
            for svc in cl.get("services", []):
                sname = svc.get("serviceName", "")
                add_node(f"ecs-svc:{cname}/{sname}", sname, "ecs-service", region, "ecs", {
                    "launch_type": svc.get("launchType"),
                    "desired": svc.get("desiredCount"),
                    "running": svc.get("runningCount"),
                })
                add_edge(f"ecs-cluster:{cname}", f"ecs-svc:{cname}/{sname}", "runs", "compute")
                net_cfg = svc.get("networkConfiguration", {}).get("awsvpcConfiguration", {})
                for sid in net_cfg.get("subnets", []):
                    add_edge(f"subnet:{sid}", f"ecs-svc:{cname}/{sname}", "hosts", "network")
                for sg in net_cfg.get("securityGroups", []):
                    add_edge(f"ecs-svc:{cname}/{sname}", f"sg:{sg}", "member-of", "security")

        # --- EKS ---
        eks = services.get("eks", {})
        for cl in eks.get("clusters", []):
            cname = cl.get("name", "")
            add_node(f"eks:{cname}", cname, "eks-cluster", region, "eks", {
                "status": cl.get("status"),
                "version": cl.get("version"),
            })
            vpc_id = cl.get("resourcesVpcConfig", {}).get("vpcId")
            if vpc_id:
                add_edge(f"vpc:{vpc_id}", f"eks:{cname}", "hosts", "network")

        # --- ELB ---
        elb = services.get("elb", {})
        for lb in elb.get("load_balancers_v2", []):
            lbn = lb.get("LoadBalancerName", "")
            lba = lb.get("LoadBalancerArn", "")
            dns = lb.get("DNSName", "")
            vpc_id = lb.get("VpcId")
            lb_sgs = lb.get("SecurityGroups", [])
            add_node(f"alb:{lbn}", f"{lbn} ({lb.get('Type', 'alb')})", "load-balancer", region, "elb", {
                "dns": dns,
                "type": lb.get("Type"),
                "state": lb.get("State", {}).get("Code"),
            })
            if vpc_id:
                add_edge(f"vpc:{vpc_id}", f"alb:{lbn}", "hosts", "network")
            for sg in lb_sgs:
                add_edge(f"alb:{lbn}", f"sg:{sg}", "member-of", "security")
            # Subnets
            for az in lb.get("AvailabilityZones", []):
                sid = az.get("SubnetId")
                if sid:
                    add_edge(f"subnet:{sid}", f"alb:{lbn}", "hosts", "network")

        for tg in elb.get("target_groups", []):
            tgn = tg.get("TargetGroupName", "")
            add_node(f"tg:{tgn}", tgn, "target-group", region, "elb", {
                "protocol": tg.get("Protocol"),
                "port": tg.get("Port"),
                "target_type": tg.get("TargetType"),
            })
            for lba in tg.get("LoadBalancerArns", []):
                # find ALB name from arn
                for lb in elb.get("load_balancers_v2", []):
                    if lb.get("LoadBalancerArn") == lba:
                        add_edge(f"alb:{lb['LoadBalancerName']}", f"tg:{tgn}", "routes-to", "network")

        # --- DynamoDB ---
        ddb = services.get("dynamodb", {})
        for t in ddb.get("tables", []):
            tname = t.get("TableName", "")
            add_node(f"ddb:{tname}", tname, "dynamodb-table", region, "dynamodb", {
                "status": t.get("TableStatus"),
                "item_count": t.get("ItemCount"),
            })

        # --- SQS ---
        sqs = services.get("sqs", {})
        for q in sqs.get("queues", []):
            url = q.get("url", "")
            qname = url.split("/")[-1] if url else ""
            add_node(f"sqs:{qname}", qname, "sqs-queue", region, "sqs", {
                "messages": q.get("attributes", {}).get("ApproximateNumberOfMessages"),
            })

        # --- SNS ---
        sns = services.get("sns", {})
        for t in sns.get("topics", []):
            arn = t.get("TopicArn", "")
            tname = arn.split(":")[-1] if arn else ""
            display = t.get("attributes", {}).get("DisplayName") or tname
            add_node(f"sns:{tname}", display, "sns-topic", region, "sns")

        # --- Secrets Manager ---
        sm = services.get("secrets_manager", {})
        for s in sm.get("secrets", []):
            sname = s.get("Name", "")
            add_node(f"secret:{sname}", sname, "secret", region, "secrets_manager")

        # --- KMS ---
        kms = services.get("kms", {})
        for k in kms.get("keys", []):
            kid = k.get("KeyId", "")
            desc = k.get("Description") or kid
            add_node(f"kms:{kid}", desc, "kms-key", region, "kms", {
                "state": k.get("KeyState"),
            })

        # --- CloudFormation ---
        cfn = services.get("cloudformation", {})
        for st in cfn.get("stacks", []):
            sname = st.get("StackName", "")
            add_node(f"cfn:{sname}", sname, "cfn-stack", region, "cloudformation", {
                "status": st.get("StackStatus"),
            })

        # --- API Gateway ---
        apigw = services.get("api_gateway", {})
        for api in apigw.get("rest_apis", []):
            aid = api.get("id", "")
            aname = api.get("name", aid)
            add_node(f"apigw:{aid}", aname, "api-gateway", region, "api_gateway")

        # --- ACM ---
        acm_data = services.get("acm", {})
        for cert in acm_data.get("certificates", []):
            carn = cert.get("CertificateArn", "")
            domain = cert.get("DomainName", carn)
            add_node(f"acm:{domain}", domain, "acm-cert", region, "acm", {
                "status": cert.get("Status"),
            })

        # --- CloudTrail ---
        ct = services.get("cloudtrail", {})
        for tr in ct.get("trails", []):
            tname = tr.get("Name", "")
            s3b = tr.get("S3BucketName")
            add_node(f"trail:{tname}", tname, "cloudtrail", region, "cloudtrail", {
                "multi_region": tr.get("IsMultiRegionTrail"),
            })
            if s3b and f"s3:{s3b}" in seen_ids:
                add_edge(f"trail:{tname}", f"s3:{s3b}", "logs-to", "logging")

        # --- ElastiCache ---
        ecache = services.get("elasticache", {})
        for c in ecache.get("clusters", []):
            cid = c.get("CacheClusterId", "")
            add_node(f"ecache:{cid}", cid, "elasticache-cluster", region, "elasticache", {
                "engine": c.get("Engine"),
                "status": c.get("CacheClusterStatus"),
            })

        # --- EFS ---
        efs_data = services.get("efs", {})
        for fs in efs_data.get("file_systems", []):
            fsid = fs.get("FileSystemId", "")
            fsname = fs.get("Name") or fsid
            add_node(f"efs:{fsid}", fsname, "efs", region, "efs")

    # =========================================================================
    # DERIVED EDGES: Security group cross-references (reachability)
    # =========================================================================
    for target_sg, source_sgs in sg_inbound_refs.items():
        for source_sg in source_sgs:
            add_edge(f"sg:{source_sg}", f"sg:{target_sg}", "allows-traffic-to", "security-flow")

    # =========================================================================
    # ERROR NODES (access-denied markers)
    # =========================================================================
    all_errors = inventory.get("errors", {})
    error_count = 0
    for e in all_errors.get("global", []):
        error_count += 1
        add_node(f"error:global:{error_count}", f"⚠ {e['resource']}", "error", "global", "error", {
            "code": e.get("code"),
            "message": e.get("message"),
        })
    for reg, errs in all_errors.get("regional", {}).items():
        for e in errs:
            error_count += 1
            add_node(f"error:{reg}:{error_count}", f"⚠ {e['resource']}", "error", reg, "error", {
                "code": e.get("code"),
                "message": e.get("message"),
            })

    return {"nodes": nodes, "edges": edges}


def get_filters(graph_data):
    """Extract unique regions and services for filter UI."""
    regions = sorted(set(n["region"] for n in graph_data["nodes"]))
    services = sorted(set(n["service"] for n in graph_data["nodes"]))
    types = sorted(set(n["type"] for n in graph_data["nodes"]))
    return {"regions": regions, "services": services, "types": types}


def compute_stats(inventory):
    """High-level stats from inventory."""
    gs = inventory.get("global_services", {})
    rs = inventory.get("regional_services", {})
    meta = inventory.get("metadata", {})

    total_instances = 0
    total_vpcs = 0
    total_lambdas = 0
    total_rds = 0
    regions_active = len(rs)

    for region, services in rs.items():
        ec2 = services.get("ec2", {})
        for res in ec2.get("instances", []):
            total_instances += len(res.get("Instances", []))
        total_vpcs += len(ec2.get("vpcs", []))
        total_lambdas += len(services.get("lambda", {}).get("functions", []))
        total_rds += len(services.get("rds", {}).get("db_instances", []))

    return {
        "ingestion_time": meta.get("ingestion_time", "unknown"),
        "regions_scanned": len(meta.get("regions_scanned", [])),
        "regions_active": regions_active,
        "s3_buckets": len(gs.get("s3", {}).get("buckets", [])),
        "iam_users": len(gs.get("iam", {}).get("users", [])),
        "iam_roles": len(gs.get("iam", {}).get("roles", [])),
        "ec2_instances": total_instances,
        "vpcs": total_vpcs,
        "lambda_functions": total_lambdas,
        "rds_instances": total_rds,
        "total_errors": meta.get("summary", {}).get("total_errors", 0),
    }
