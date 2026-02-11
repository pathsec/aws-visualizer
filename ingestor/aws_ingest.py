#!/usr/bin/env python3
"""
AWS Environment Ingestion Tool
===============================
Enumerates as much information as possible about an AWS environment.
Gracefully handles permission errors (AccessDenied) without failing.
Exports all collected data to a JSON file for later analysis.

Usage:
    python aws_ingest.py [--regions us-east-1,us-west-2] [--output aws_inventory.json] [--profile myprofile]

Requirements:
    pip install boto3
"""

import argparse
import boto3
import json
import sys
import datetime
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DateTimeEncoder(json.JSONEncoder):
    """Handle datetime objects in JSON serialization."""
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


def safe_call(client, method, key=None, paginate=False, errors_list=None,
              service_name="", resource_name="", **kwargs):
    """
    Call a boto3 client method safely.
    - If paginate=True, uses the client's paginator.
    - Catches AccessDenied / UnauthorizedAccess and records them.
    - Returns the collected results or an empty list/dict.
    """
    label = f"{service_name}:{resource_name}" if service_name else method
    try:
        if paginate:
            paginator = client.get_paginator(method)
            results = []
            for page in paginator.paginate(**kwargs):
                if key:
                    results.extend(page.get(key, []))
                else:
                    results.append(page)
            return results
        else:
            resp = getattr(client, method)(**kwargs)
            resp.pop("ResponseMetadata", None)
            if key:
                return resp.get(key, resp)
            return resp
    except client.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        if errors_list is not None:
            errors_list.append({"resource": label, "code": code, "message": msg})
        return [] if (paginate or key) else {}
    except Exception as e:
        if errors_list is not None:
            errors_list.append({"resource": label, "code": type(e).__name__, "message": str(e)})
        return [] if (paginate or key) else {}


# ---------------------------------------------------------------------------
# Global (non-regional) collectors
# ---------------------------------------------------------------------------

def collect_iam(session, errors):
    """IAM is global."""
    iam = session.client("iam", region_name="us-east-1")
    data = {}
    data["users"] = safe_call(iam, "list_users", key="Users", paginate=True,
                              errors_list=errors, service_name="iam", resource_name="users")
    data["groups"] = safe_call(iam, "list_groups", key="Groups", paginate=True,
                               errors_list=errors, service_name="iam", resource_name="groups")
    data["roles"] = safe_call(iam, "list_roles", key="Roles", paginate=True,
                              errors_list=errors, service_name="iam", resource_name="roles")
    data["policies"] = safe_call(iam, "list_policies", key="Policies", paginate=True,
                                 errors_list=errors, service_name="iam", resource_name="policies",
                                 Scope="Local")
    data["instance_profiles"] = safe_call(iam, "list_instance_profiles", key="InstanceProfiles",
                                          paginate=True, errors_list=errors, service_name="iam",
                                          resource_name="instance_profiles")
    data["account_summary"] = safe_call(iam, "get_account_summary", key="SummaryMap",
                                        errors_list=errors, service_name="iam",
                                        resource_name="account_summary")
    data["account_aliases"] = safe_call(iam, "list_account_aliases", key="AccountAliases",
                                        paginate=True, errors_list=errors, service_name="iam",
                                        resource_name="account_aliases")
    # MFA devices per user
    for user in data.get("users", []):
        uname = user.get("UserName", "")
        user["mfa_devices"] = safe_call(iam, "list_mfa_devices", key="MFADevices",
                                        errors_list=errors, service_name="iam",
                                        resource_name=f"mfa_devices/{uname}",
                                        UserName=uname)
        user["access_keys"] = safe_call(iam, "list_access_keys", key="AccessKeyMetadata",
                                        errors_list=errors, service_name="iam",
                                        resource_name=f"access_keys/{uname}",
                                        UserName=uname)
        user["attached_policies"] = safe_call(iam, "list_attached_user_policies",
                                              key="AttachedPolicies", paginate=True,
                                              errors_list=errors, service_name="iam",
                                              resource_name=f"user_policies/{uname}",
                                              UserName=uname)
    return data


def collect_s3(session, errors):
    """S3 is global (bucket list), but we gather per-bucket details."""
    s3 = session.client("s3", region_name="us-east-1")
    buckets = safe_call(s3, "list_buckets", key="Buckets", errors_list=errors,
                        service_name="s3", resource_name="list_buckets")
    for b in buckets:
        name = b["Name"]
        b["acl"] = safe_call(s3, "get_bucket_acl", errors_list=errors,
                             service_name="s3", resource_name=f"acl/{name}", Bucket=name)
        b["versioning"] = safe_call(s3, "get_bucket_versioning", errors_list=errors,
                                    service_name="s3", resource_name=f"versioning/{name}",
                                    Bucket=name)
        b["encryption"] = safe_call(s3, "get_bucket_encryption", errors_list=errors,
                                    service_name="s3", resource_name=f"encryption/{name}",
                                    Bucket=name)
        b["public_access_block"] = safe_call(s3, "get_public_access_block", errors_list=errors,
                                             service_name="s3",
                                             resource_name=f"public_access/{name}",
                                             Bucket=name)
        b["logging"] = safe_call(s3, "get_bucket_logging", errors_list=errors,
                                 service_name="s3", resource_name=f"logging/{name}",
                                 Bucket=name)
        b["tagging"] = safe_call(s3, "get_bucket_tagging", key="TagSet", errors_list=errors,
                                 service_name="s3", resource_name=f"tagging/{name}",
                                 Bucket=name)
        b["policy"] = safe_call(s3, "get_bucket_policy", key="Policy", errors_list=errors,
                                service_name="s3", resource_name=f"policy/{name}",
                                Bucket=name)
        b["lifecycle"] = safe_call(s3, "get_bucket_lifecycle_configuration", key="Rules",
                                   errors_list=errors, service_name="s3",
                                   resource_name=f"lifecycle/{name}", Bucket=name)
    return {"buckets": buckets}


def collect_route53(session, errors):
    r53 = session.client("route53", region_name="us-east-1")
    zones = safe_call(r53, "list_hosted_zones", key="HostedZones", paginate=True,
                      errors_list=errors, service_name="route53", resource_name="hosted_zones")
    for z in zones:
        zid = z["Id"].split("/")[-1]
        z["record_sets"] = safe_call(r53, "list_resource_record_sets",
                                     key="ResourceRecordSets", paginate=True,
                                     errors_list=errors, service_name="route53",
                                     resource_name=f"records/{zid}", HostedZoneId=zid)
    return {"hosted_zones": zones}


def collect_organizations(session, errors):
    org = session.client("organizations", region_name="us-east-1")
    data = {}
    data["organization"] = safe_call(org, "describe_organization", key="Organization",
                                     errors_list=errors, service_name="organizations",
                                     resource_name="describe")
    data["accounts"] = safe_call(org, "list_accounts", key="Accounts", paginate=True,
                                 errors_list=errors, service_name="organizations",
                                 resource_name="accounts")
    return data


def collect_cloudfront(session, errors):
    cf = session.client("cloudfront", region_name="us-east-1")
    dists = safe_call(cf, "list_distributions", errors_list=errors,
                      service_name="cloudfront", resource_name="distributions")
    items = []
    if isinstance(dists, dict):
        dl = dists.get("DistributionList", {})
        items = dl.get("Items", []) if isinstance(dl, dict) else []
    return {"distributions": items}


# ---------------------------------------------------------------------------
# Regional collectors
# ---------------------------------------------------------------------------

def collect_ec2(session, region, errors):
    ec2 = session.client("ec2", region_name=region)
    data = {}
    data["instances"] = safe_call(ec2, "describe_instances", key="Reservations", paginate=True,
                                  errors_list=errors, service_name="ec2", resource_name="instances")
    data["vpcs"] = safe_call(ec2, "describe_vpcs", key="Vpcs",
                             errors_list=errors, service_name="ec2", resource_name="vpcs")
    data["subnets"] = safe_call(ec2, "describe_subnets", key="Subnets",
                                errors_list=errors, service_name="ec2", resource_name="subnets")
    data["security_groups"] = safe_call(ec2, "describe_security_groups", key="SecurityGroups",
                                        errors_list=errors, service_name="ec2",
                                        resource_name="security_groups")
    data["volumes"] = safe_call(ec2, "describe_volumes", key="Volumes", paginate=True,
                                errors_list=errors, service_name="ec2", resource_name="volumes")
    data["snapshots"] = safe_call(ec2, "describe_snapshots", key="Snapshots", paginate=True,
                                  errors_list=errors, service_name="ec2", resource_name="snapshots",
                                  OwnerIds=["self"])
    data["amis"] = safe_call(ec2, "describe_images", key="Images",
                             errors_list=errors, service_name="ec2", resource_name="amis",
                             Owners=["self"])
    data["key_pairs"] = safe_call(ec2, "describe_key_pairs", key="KeyPairs",
                                  errors_list=errors, service_name="ec2", resource_name="key_pairs")
    data["elastic_ips"] = safe_call(ec2, "describe_addresses", key="Addresses",
                                    errors_list=errors, service_name="ec2",
                                    resource_name="elastic_ips")
    data["network_interfaces"] = safe_call(ec2, "describe_network_interfaces",
                                           key="NetworkInterfaces", paginate=True,
                                           errors_list=errors, service_name="ec2",
                                           resource_name="network_interfaces")
    data["internet_gateways"] = safe_call(ec2, "describe_internet_gateways",
                                          key="InternetGateways", errors_list=errors,
                                          service_name="ec2", resource_name="internet_gateways")
    data["nat_gateways"] = safe_call(ec2, "describe_nat_gateways", key="NatGateways",
                                     paginate=True, errors_list=errors, service_name="ec2",
                                     resource_name="nat_gateways")
    data["route_tables"] = safe_call(ec2, "describe_route_tables", key="RouteTables",
                                     errors_list=errors, service_name="ec2",
                                     resource_name="route_tables")
    data["vpc_endpoints"] = safe_call(ec2, "describe_vpc_endpoints", key="VpcEndpoints",
                                      paginate=True, errors_list=errors, service_name="ec2",
                                      resource_name="vpc_endpoints")
    data["vpc_peering_connections"] = safe_call(ec2, "describe_vpc_peering_connections",
                                                key="VpcPeeringConnections",
                                                errors_list=errors, service_name="ec2",
                                                resource_name="vpc_peering")
    data["transit_gateways"] = safe_call(ec2, "describe_transit_gateways",
                                         key="TransitGateways", errors_list=errors,
                                         service_name="ec2", resource_name="transit_gateways")
    data["launch_templates"] = safe_call(ec2, "describe_launch_templates",
                                         key="LaunchTemplates", errors_list=errors,
                                         service_name="ec2", resource_name="launch_templates")
    data["placement_groups"] = safe_call(ec2, "describe_placement_groups",
                                         key="PlacementGroups", errors_list=errors,
                                         service_name="ec2", resource_name="placement_groups")
    data["flow_logs"] = safe_call(ec2, "describe_flow_logs", key="FlowLogs",
                                  errors_list=errors, service_name="ec2", resource_name="flow_logs")
    return data


def collect_rds(session, region, errors):
    rds = session.client("rds", region_name=region)
    data = {}
    data["db_instances"] = safe_call(rds, "describe_db_instances", key="DBInstances",
                                     paginate=True, errors_list=errors, service_name="rds",
                                     resource_name="db_instances")
    data["db_clusters"] = safe_call(rds, "describe_db_clusters", key="DBClusters",
                                    paginate=True, errors_list=errors, service_name="rds",
                                    resource_name="db_clusters")
    data["db_snapshots"] = safe_call(rds, "describe_db_snapshots", key="DBSnapshots",
                                     paginate=True, errors_list=errors, service_name="rds",
                                     resource_name="db_snapshots")
    data["db_subnet_groups"] = safe_call(rds, "describe_db_subnet_groups",
                                         key="DBSubnetGroups", paginate=True,
                                         errors_list=errors, service_name="rds",
                                         resource_name="db_subnet_groups")
    return data


def collect_lambda(session, region, errors):
    lam = session.client("lambda", region_name=region)
    funcs = safe_call(lam, "list_functions", key="Functions", paginate=True,
                      errors_list=errors, service_name="lambda", resource_name="functions")
    for f in funcs:
        fname = f["FunctionName"]
        f["policy"] = safe_call(lam, "get_policy", errors_list=errors,
                                service_name="lambda", resource_name=f"policy/{fname}",
                                FunctionName=fname)
        f["event_source_mappings"] = safe_call(lam, "list_event_source_mappings",
                                               key="EventSourceMappings",
                                               errors_list=errors, service_name="lambda",
                                               resource_name=f"event_sources/{fname}",
                                               FunctionName=fname)
    return {"functions": funcs}


def collect_ecs(session, region, errors):
    ecs = session.client("ecs", region_name=region)
    data = {}
    cluster_arns = safe_call(ecs, "list_clusters", key="clusterArns", paginate=True,
                             errors_list=errors, service_name="ecs", resource_name="clusters")
    if cluster_arns:
        data["clusters"] = safe_call(ecs, "describe_clusters", key="clusters",
                                     errors_list=errors, service_name="ecs",
                                     resource_name="describe_clusters",
                                     clusters=cluster_arns, include=["TAGS", "SETTINGS", "STATISTICS"])
        for arn in cluster_arns:
            svc_arns = safe_call(ecs, "list_services", key="serviceArns", paginate=True,
                                 errors_list=errors, service_name="ecs",
                                 resource_name=f"services/{arn}", cluster=arn)
            if svc_arns:
                # describe_services max 10 at a time
                svcs = []
                for i in range(0, len(svc_arns), 10):
                    batch = safe_call(ecs, "describe_services", key="services",
                                      errors_list=errors, service_name="ecs",
                                      resource_name="describe_services",
                                      cluster=arn, services=svc_arns[i:i+10])
                    svcs.extend(batch)
                for c in data.get("clusters", []):
                    if c.get("clusterArn") == arn:
                        c["services"] = svcs
    else:
        data["clusters"] = []
    # Task definitions
    td_arns = safe_call(ecs, "list_task_definitions", key="taskDefinitionArns", paginate=True,
                        errors_list=errors, service_name="ecs", resource_name="task_definitions")
    data["task_definition_arns"] = td_arns
    return data


def collect_eks(session, region, errors):
    eks = session.client("eks", region_name=region)
    names = safe_call(eks, "list_clusters", key="clusters", paginate=True,
                      errors_list=errors, service_name="eks", resource_name="clusters")
    clusters = []
    for name in names:
        c = safe_call(eks, "describe_cluster", key="cluster", errors_list=errors,
                      service_name="eks", resource_name=f"cluster/{name}", name=name)
        if c:
            clusters.append(c)
    return {"clusters": clusters}


def collect_elb(session, region, errors):
    elbv2 = session.client("elbv2", region_name=region)
    elb = session.client("elb", region_name=region)
    data = {}
    data["load_balancers_v2"] = safe_call(elbv2, "describe_load_balancers",
                                          key="LoadBalancers", paginate=True,
                                          errors_list=errors, service_name="elbv2",
                                          resource_name="load_balancers")
    data["target_groups"] = safe_call(elbv2, "describe_target_groups", key="TargetGroups",
                                      paginate=True, errors_list=errors, service_name="elbv2",
                                      resource_name="target_groups")
    data["classic_load_balancers"] = safe_call(elb, "describe_load_balancers",
                                               key="LoadBalancerDescriptions", paginate=True,
                                               errors_list=errors, service_name="elb",
                                               resource_name="classic_lbs")
    return data


def collect_autoscaling(session, region, errors):
    asg = session.client("autoscaling", region_name=region)
    data = {}
    data["auto_scaling_groups"] = safe_call(asg, "describe_auto_scaling_groups",
                                            key="AutoScalingGroups", paginate=True,
                                            errors_list=errors, service_name="autoscaling",
                                            resource_name="groups")
    data["launch_configurations"] = safe_call(asg, "describe_launch_configurations",
                                              key="LaunchConfigurations", paginate=True,
                                              errors_list=errors, service_name="autoscaling",
                                              resource_name="launch_configs")
    return data


def collect_dynamodb(session, region, errors):
    ddb = session.client("dynamodb", region_name=region)
    names = safe_call(ddb, "list_tables", key="TableNames", paginate=True,
                      errors_list=errors, service_name="dynamodb", resource_name="tables")
    tables = []
    for name in names:
        t = safe_call(ddb, "describe_table", key="Table", errors_list=errors,
                      service_name="dynamodb", resource_name=f"table/{name}", TableName=name)
        if t:
            tables.append(t)
    return {"tables": tables}


def collect_sqs(session, region, errors):
    sqs = session.client("sqs", region_name=region)
    urls = safe_call(sqs, "list_queues", key="QueueUrls", errors_list=errors,
                     service_name="sqs", resource_name="queues")
    queues = []
    for url in (urls or []):
        attrs = safe_call(sqs, "get_queue_attributes", key="Attributes", errors_list=errors,
                          service_name="sqs", resource_name=f"attrs/{url}",
                          QueueUrl=url, AttributeNames=["All"])
        queues.append({"url": url, "attributes": attrs})
    return {"queues": queues}


def collect_sns(session, region, errors):
    sns = session.client("sns", region_name=region)
    topics = safe_call(sns, "list_topics", key="Topics", paginate=True,
                       errors_list=errors, service_name="sns", resource_name="topics")
    for t in topics:
        arn = t["TopicArn"]
        t["attributes"] = safe_call(sns, "get_topic_attributes", key="Attributes",
                                    errors_list=errors, service_name="sns",
                                    resource_name=f"topic_attrs/{arn}", TopicArn=arn)
        t["subscriptions"] = safe_call(sns, "list_subscriptions_by_topic",
                                       key="Subscriptions", paginate=True,
                                       errors_list=errors, service_name="sns",
                                       resource_name=f"subscriptions/{arn}", TopicArn=arn)
    return {"topics": topics}


def collect_cloudwatch(session, region, errors):
    cw = session.client("cloudwatch", region_name=region)
    data = {}
    data["alarms"] = safe_call(cw, "describe_alarms", key="MetricAlarms", paginate=True,
                               errors_list=errors, service_name="cloudwatch",
                               resource_name="alarms")
    data["dashboards"] = safe_call(cw, "list_dashboards", key="DashboardEntries",
                                   paginate=True, errors_list=errors, service_name="cloudwatch",
                                   resource_name="dashboards")
    return data


def collect_cloudwatch_logs(session, region, errors):
    logs = session.client("logs", region_name=region)
    groups = safe_call(logs, "describe_log_groups", key="logGroups", paginate=True,
                       errors_list=errors, service_name="logs", resource_name="log_groups")
    return {"log_groups": groups}


def collect_cloudformation(session, region, errors):
    cfn = session.client("cloudformation", region_name=region)
    stacks = safe_call(cfn, "describe_stacks", key="Stacks", errors_list=errors,
                       service_name="cloudformation", resource_name="stacks")
    return {"stacks": stacks if isinstance(stacks, list) else []}


def collect_secrets_manager(session, region, errors):
    sm = session.client("secretsmanager", region_name=region)
    secrets = safe_call(sm, "list_secrets", key="SecretList", paginate=True,
                        errors_list=errors, service_name="secretsmanager",
                        resource_name="secrets")
    return {"secrets": secrets}


def collect_ssm(session, region, errors):
    ssm = session.client("ssm", region_name=region)
    params = safe_call(ssm, "describe_parameters", key="Parameters", paginate=True,
                       errors_list=errors, service_name="ssm", resource_name="parameters")
    return {"parameters": params}


def collect_kms(session, region, errors):
    kms = session.client("kms", region_name=region)
    keys = safe_call(kms, "list_keys", key="Keys", paginate=True,
                     errors_list=errors, service_name="kms", resource_name="keys")
    detailed = []
    for k in keys:
        kid = k["KeyId"]
        meta = safe_call(kms, "describe_key", key="KeyMetadata", errors_list=errors,
                         service_name="kms", resource_name=f"key/{kid}", KeyId=kid)
        if meta:
            detailed.append(meta)
    return {"keys": detailed}


def collect_ecr(session, region, errors):
    ecr = session.client("ecr", region_name=region)
    repos = safe_call(ecr, "describe_repositories", key="repositories", paginate=True,
                      errors_list=errors, service_name="ecr", resource_name="repositories")
    for r in repos:
        rname = r["repositoryName"]
        r["images"] = safe_call(ecr, "list_images", key="imageIds", paginate=True,
                                errors_list=errors, service_name="ecr",
                                resource_name=f"images/{rname}",
                                repositoryName=rname)
    return {"repositories": repos}


def collect_elasticache(session, region, errors):
    ec = session.client("elasticache", region_name=region)
    data = {}
    data["clusters"] = safe_call(ec, "describe_cache_clusters", key="CacheClusters",
                                 paginate=True, errors_list=errors,
                                 service_name="elasticache", resource_name="clusters")
    data["replication_groups"] = safe_call(ec, "describe_replication_groups",
                                           key="ReplicationGroups", paginate=True,
                                           errors_list=errors, service_name="elasticache",
                                           resource_name="replication_groups")
    return data


def collect_kinesis(session, region, errors):
    kin = session.client("kinesis", region_name=region)
    names = safe_call(kin, "list_streams", key="StreamNames", paginate=True,
                      errors_list=errors, service_name="kinesis", resource_name="streams")
    streams = []
    for name in names:
        s = safe_call(kin, "describe_stream", key="StreamDescription",
                      errors_list=errors, service_name="kinesis",
                      resource_name=f"stream/{name}", StreamName=name)
        if s:
            streams.append(s)
    return {"streams": streams}


def collect_step_functions(session, region, errors):
    sf = session.client("stepfunctions", region_name=region)
    machines = safe_call(sf, "list_state_machines", key="stateMachines", paginate=True,
                         errors_list=errors, service_name="stepfunctions",
                         resource_name="state_machines")
    return {"state_machines": machines}


def collect_api_gateway(session, region, errors):
    apigw = session.client("apigateway", region_name=region)
    apis = safe_call(apigw, "get_rest_apis", key="items", paginate=True,
                     errors_list=errors, service_name="apigateway", resource_name="rest_apis")
    # Also v2 (HTTP & WebSocket)
    apigw2 = session.client("apigatewayv2", region_name=region)
    v2_apis = safe_call(apigw2, "get_apis", key="Items", errors_list=errors,
                        service_name="apigatewayv2", resource_name="apis")
    return {"rest_apis": apis, "http_websocket_apis": v2_apis if isinstance(v2_apis, list) else []}


def collect_redshift(session, region, errors):
    rs = session.client("redshift", region_name=region)
    clusters = safe_call(rs, "describe_clusters", key="Clusters", paginate=True,
                         errors_list=errors, service_name="redshift", resource_name="clusters")
    return {"clusters": clusters}


def collect_glue(session, region, errors):
    glue = session.client("glue", region_name=region)
    data = {}
    data["databases"] = safe_call(glue, "get_databases", key="DatabaseList", paginate=True,
                                  errors_list=errors, service_name="glue",
                                  resource_name="databases")
    data["crawlers"] = safe_call(glue, "get_crawlers", key="Crawlers", paginate=True,
                                 errors_list=errors, service_name="glue",
                                 resource_name="crawlers")
    data["jobs"] = safe_call(glue, "get_jobs", key="Jobs", paginate=True,
                             errors_list=errors, service_name="glue", resource_name="jobs")
    return data


def collect_cloudtrail(session, region, errors):
    ct = session.client("cloudtrail", region_name=region)
    trails = safe_call(ct, "describe_trails", key="trailList", errors_list=errors,
                       service_name="cloudtrail", resource_name="trails")
    return {"trails": trails if isinstance(trails, list) else []}


def collect_config(session, region, errors):
    cfg = session.client("config", region_name=region)
    recorders = safe_call(cfg, "describe_configuration_recorders",
                          key="ConfigurationRecorders", errors_list=errors,
                          service_name="config", resource_name="recorders")
    rules = safe_call(cfg, "describe_config_rules", key="ConfigRules", errors_list=errors,
                      service_name="config", resource_name="rules")
    return {"recorders": recorders if isinstance(recorders, list) else [],
            "rules": rules if isinstance(rules, list) else []}


def collect_wafv2(session, region, errors):
    waf = session.client("wafv2", region_name=region)
    regional = safe_call(waf, "list_web_acls", key="WebACLs", errors_list=errors,
                         service_name="wafv2", resource_name="web_acls",
                         Scope="REGIONAL")
    return {"web_acls": regional if isinstance(regional, list) else []}


def collect_acm(session, region, errors):
    acm = session.client("acm", region_name=region)
    certs = safe_call(acm, "list_certificates", key="CertificateSummaryList", paginate=True,
                      errors_list=errors, service_name="acm", resource_name="certificates")
    return {"certificates": certs}


def collect_sagemaker(session, region, errors):
    sm = session.client("sagemaker", region_name=region)
    data = {}
    data["notebooks"] = safe_call(sm, "list_notebook_instances", key="NotebookInstances",
                                  paginate=True, errors_list=errors, service_name="sagemaker",
                                  resource_name="notebooks")
    data["endpoints"] = safe_call(sm, "list_endpoints", key="Endpoints", paginate=True,
                                  errors_list=errors, service_name="sagemaker",
                                  resource_name="endpoints")
    data["models"] = safe_call(sm, "list_models", key="Models", paginate=True,
                               errors_list=errors, service_name="sagemaker",
                               resource_name="models")
    return data


def collect_emr(session, region, errors):
    emr = session.client("emr", region_name=region)
    clusters = safe_call(emr, "list_clusters", key="Clusters", paginate=True,
                         errors_list=errors, service_name="emr", resource_name="clusters")
    return {"clusters": clusters}


def collect_opensearch(session, region, errors):
    os_client = session.client("opensearch", region_name=region)
    names = safe_call(os_client, "list_domain_names", key="DomainNames",
                      errors_list=errors, service_name="opensearch",
                      resource_name="domain_names")
    domains = []
    if names:
        dnames = [d["DomainName"] for d in names if "DomainName" in d]
        if dnames:
            resp = safe_call(os_client, "describe_domains", key="DomainStatusList",
                             errors_list=errors, service_name="opensearch",
                             resource_name="domains", DomainNames=dnames[:5])
            domains = resp if isinstance(resp, list) else []
    return {"domains": domains}


def collect_backup(session, region, errors):
    bk = session.client("backup", region_name=region)
    vaults = safe_call(bk, "list_backup_vaults", key="BackupVaultList", errors_list=errors,
                       service_name="backup", resource_name="vaults")
    plans = safe_call(bk, "list_backup_plans", key="BackupPlansList", errors_list=errors,
                      service_name="backup", resource_name="plans")
    return {"vaults": vaults if isinstance(vaults, list) else [],
            "plans": plans if isinstance(plans, list) else []}


def collect_eventbridge(session, region, errors):
    eb = session.client("events", region_name=region)
    buses = safe_call(eb, "list_event_buses", key="EventBuses", errors_list=errors,
                      service_name="events", resource_name="event_buses")
    rules = safe_call(eb, "list_rules", key="Rules", errors_list=errors,
                      service_name="events", resource_name="rules")
    return {"event_buses": buses if isinstance(buses, list) else [],
            "rules": rules if isinstance(rules, list) else []}


def collect_efs(session, region, errors):
    efs = session.client("efs", region_name=region)
    fs = safe_call(efs, "describe_file_systems", key="FileSystems", errors_list=errors,
                   service_name="efs", resource_name="file_systems")
    return {"file_systems": fs if isinstance(fs, list) else []}


def collect_guardduty(session, region, errors):
    gd = session.client("guardduty", region_name=region)
    detectors = safe_call(gd, "list_detectors", key="DetectorIds", errors_list=errors,
                          service_name="guardduty", resource_name="detectors")
    return {"detector_ids": detectors if isinstance(detectors, list) else []}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

ALL_AWS_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "af-south-1", "ap-east-1", "ap-south-1", "ap-south-2",
    "ap-southeast-1", "ap-southeast-2", "ap-southeast-3", "ap-southeast-4",
    "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
    "ca-central-1", "ca-west-1",
    "eu-central-1", "eu-central-2",
    "eu-west-1", "eu-west-2", "eu-west-3",
    "eu-north-1", "eu-south-1", "eu-south-2",
    "il-central-1",
    "me-central-1", "me-south-1",
    "sa-east-1",
]

REGIONAL_COLLECTORS = {
    "ec2": collect_ec2,
    "rds": collect_rds,
    "lambda": collect_lambda,
    "ecs": collect_ecs,
    "eks": collect_eks,
    "elb": collect_elb,
    "autoscaling": collect_autoscaling,
    "dynamodb": collect_dynamodb,
    "sqs": collect_sqs,
    "sns": collect_sns,
    "cloudwatch": collect_cloudwatch,
    "cloudwatch_logs": collect_cloudwatch_logs,
    "cloudformation": collect_cloudformation,
    "secrets_manager": collect_secrets_manager,
    "ssm": collect_ssm,
    "kms": collect_kms,
    "ecr": collect_ecr,
    "elasticache": collect_elasticache,
    "kinesis": collect_kinesis,
    "step_functions": collect_step_functions,
    "api_gateway": collect_api_gateway,
    "redshift": collect_redshift,
    "glue": collect_glue,
    "cloudtrail": collect_cloudtrail,
    "config": collect_config,
    "wafv2": collect_wafv2,
    "acm": collect_acm,
    "sagemaker": collect_sagemaker,
    "emr": collect_emr,
    "opensearch": collect_opensearch,
    "backup": collect_backup,
    "eventbridge": collect_eventbridge,
    "efs": collect_efs,
    "guardduty": collect_guardduty,
}


def collect_region(session, region):
    """Run all regional collectors for a single region."""
    print(f"  ⏳  Scanning region: {region}")
    region_data = {}
    region_errors = []

    for service_name, collector_fn in REGIONAL_COLLECTORS.items():
        try:
            region_data[service_name] = collector_fn(session, region, region_errors)
        except Exception as e:
            region_errors.append({
                "resource": f"{service_name}:*",
                "code": type(e).__name__,
                "message": str(e),
            })

    # Drop services with all-empty data to keep output clean
    region_data = {k: v for k, v in region_data.items() if _has_data(v)}

    print(f"  ✅  {region}: {len(region_data)} services with data, {len(region_errors)} errors")
    return region, region_data, region_errors


def _has_data(obj):
    """Check if a dict of lists has any non-empty values."""
    if isinstance(obj, dict):
        return any(
            (isinstance(v, list) and len(v) > 0) or
            (isinstance(v, dict) and len(v) > 0) or
            (isinstance(v, str) and len(v) > 0)
            for v in obj.values()
        )
    return bool(obj)


def main():
    parser = argparse.ArgumentParser(description="AWS Environment Ingestion Tool")
    parser.add_argument("--regions", type=str, default=None,
                        help="Comma-separated list of regions (default: all)")
    parser.add_argument("--output", type=str, default="aws_inventory.json",
                        help="Output JSON file path (default: aws_inventory.json)")
    parser.add_argument("--profile", type=str, default=None,
                        help="AWS CLI profile name")
    parser.add_argument("--max-workers", type=int, default=4,
                        help="Parallel region scanning threads (default: 4)")
    args = parser.parse_args()

    # Build session
    session_kwargs = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)

    # Determine regions
    if args.regions:
        regions = [r.strip() for r in args.regions.split(",")]
    else:
        regions = ALL_AWS_REGIONS

    inventory = {
        "metadata": {
            "ingestion_time": datetime.datetime.utcnow().isoformat() + "Z",
            "regions_scanned": regions,
            "profile": args.profile or "default",
        },
        "global_services": {},
        "regional_services": {},
        "errors": {
            "global": [],
            "regional": defaultdict(list),
        },
    }

    # ------------------------------------------------------------------
    # 1. Global services
    # ------------------------------------------------------------------
    print("=" * 60)
    print("  AWS ENVIRONMENT INGESTION TOOL")
    print("=" * 60)
    print()
    print("[GLOBAL SERVICES]")

    global_errors = inventory["errors"]["global"]

    print("  ⏳  IAM ...")
    inventory["global_services"]["iam"] = collect_iam(session, global_errors)
    print("  ⏳  S3 ...")
    inventory["global_services"]["s3"] = collect_s3(session, global_errors)
    print("  ⏳  Route53 ...")
    inventory["global_services"]["route53"] = collect_route53(session, global_errors)
    print("  ⏳  Organizations ...")
    inventory["global_services"]["organizations"] = collect_organizations(session, global_errors)
    print("  ⏳  CloudFront ...")
    inventory["global_services"]["cloudfront"] = collect_cloudfront(session, global_errors)

    print(f"  ✅  Global: {len(global_errors)} errors recorded\n")

    # ------------------------------------------------------------------
    # 2. Regional services (parallel)
    # ------------------------------------------------------------------
    print(f"[REGIONAL SERVICES — {len(regions)} regions, {args.max_workers} workers]")

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(collect_region, session, region): region
            for region in regions
        }
        for future in as_completed(futures):
            region, region_data, region_errors = future.result()
            if region_data:
                inventory["regional_services"][region] = region_data
            if region_errors:
                inventory["errors"]["regional"][region] = region_errors

    # Convert defaultdict for JSON
    inventory["errors"]["regional"] = dict(inventory["errors"]["regional"])

    # ------------------------------------------------------------------
    # 3. Summary
    # ------------------------------------------------------------------
    total_errors = len(global_errors) + sum(
        len(v) for v in inventory["errors"]["regional"].values()
    )
    regions_with_data = len(inventory["regional_services"])
    total_services = sum(
        len(v) for v in inventory["regional_services"].values()
    )

    inventory["metadata"]["summary"] = {
        "regions_with_resources": regions_with_data,
        "total_regional_service_region_pairs": total_services,
        "total_errors": total_errors,
        "global_services_collected": list(inventory["global_services"].keys()),
    }

    # ------------------------------------------------------------------
    # 4. Write output
    # ------------------------------------------------------------------
    with open(args.output, "w") as f:
        json.dump(inventory, f, cls=DateTimeEncoder, indent=2, default=str)

    size_mb = round(len(json.dumps(inventory, cls=DateTimeEncoder, default=str)) / 1024 / 1024, 2)

    print()
    print("=" * 60)
    print(f"  DONE — Inventory written to: {args.output}")
    print(f"  Approximate size: {size_mb} MB")
    print(f"  Regions with data: {regions_with_data}/{len(regions)}")
    print(f"  Total access errors: {total_errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()
