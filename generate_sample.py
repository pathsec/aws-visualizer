#!/usr/bin/env python3
"""
Sample AWS Inventory Generator
================================
Generates a realistic medium-sized fake AWS inventory JSON for testing the
aws-visualizer. All IDs and ARNs are internally consistent — VPC/subnet/SG
cross-references are valid within the generated data.

Usage:
    python generate_sample.py [--output sample.json] [--seed 42]

Re-run with a different --seed to get a fresh randomised inventory.
"""

import argparse
import datetime
import json
import random
import string
import uuid


ACCOUNT_ID = "123456789012"


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def _hex(n: int) -> str:
    return "".join(random.choices(string.hexdigits[:16], k=n))


def ec2id(prefix: str) -> str:
    return f"{prefix}-{_hex(8)}"


def arnf(service: str, region: str, resource: str) -> str:
    return f"arn:aws:{service}:{region}:{ACCOUNT_ID}:{resource}"


def tag(k: str, v: str) -> dict:
    return {"Key": k, "Value": v}


def tags(*pairs) -> list:
    it = iter(pairs)
    return [tag(k, v) for k, v in zip(it, it)]


# ---------------------------------------------------------------------------
# Global services
# ---------------------------------------------------------------------------

def build_iam() -> dict:
    # ── Managed policy documents ────────────────────────────────────────────
    # These are customer-managed policies with full policy documents so that
    # the IAM attack path analyser can evaluate effective permissions.
    deploy_policy_arn  = arnf("iam", "", "policy/DeployPolicy")
    s3data_policy_arn  = arnf("iam", "", "policy/S3DataReadPolicy")
    ecs_policy_arn     = arnf("iam", "", "policy/ECSTaskPolicy")
    infra_policy_arn   = arnf("iam", "", "policy/InfraMgmtPolicy")

    policies = [
        # DeployPolicy — CI/CD user; has iam:CreatePolicyVersion + lambda escalation perms
        {
            "PolicyName": "DeployPolicy",
            "PolicyId":   f"ANPA{_hex(16).upper()}",
            "Arn": deploy_policy_arn,
            "DefaultVersionId": "v3",
            "AttachmentCount": 1,
            "document": {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": [
                        "iam:CreatePolicyVersion",
                        "iam:SetDefaultPolicyVersion",
                        "lambda:UpdateFunctionCode",
                        "lambda:UpdateFunctionConfiguration",
                        "lambda:InvokeFunction",
                        "s3:GetObject", "s3:PutObject",
                        "ecr:GetAuthorizationToken", "ecr:BatchGetImage",
                        "codedeploy:*",
                    ], "Resource": "*"},
                ],
            },
        },
        # S3DataReadPolicy — data analyst; has Glue + iam:PassRole escalation vector
        {
            "PolicyName": "S3DataReadPolicy",
            "PolicyId":   f"ANPA{_hex(16).upper()}",
            "Arn": s3data_policy_arn,
            "DefaultVersionId": "v1",
            "AttachmentCount": 2,
            "document": {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": [
                        "s3:GetObject", "s3:ListBucket", "s3:ListAllMyBuckets",
                        "glue:GetJob", "glue:StartJobRun", "glue:UpdateJob",
                        "glue:CreateJob",
                        "iam:PassRole",
                        "athena:StartQueryExecution", "athena:GetQueryResults",
                    ], "Resource": "*"},
                ],
            },
        },
        # ECSTaskPolicy — ECS task role
        {
            "PolicyName": "ECSTaskPolicy",
            "PolicyId":   f"ANPA{_hex(16).upper()}",
            "Arn": ecs_policy_arn,
            "DefaultVersionId": "v1",
            "AttachmentCount": 1,
            "document": {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": [
                        "secretsmanager:GetSecretValue",
                        "ssm:GetParameter", "ssm:GetParameters",
                        "s3:GetObject",
                        "logs:CreateLogStream", "logs:PutLogEvents",
                    ], "Resource": "*"},
                ],
            },
        },
        # InfraMgmtPolicy — devops role; broad EC2 + CloudFormation + iam:PassRole
        {
            "PolicyName": "InfraMgmtPolicy",
            "PolicyId":   f"ANPA{_hex(16).upper()}",
            "Arn": infra_policy_arn,
            "DefaultVersionId": "v2",
            "AttachmentCount": 1,
            "document": {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": [
                        "ec2:RunInstances", "ec2:Describe*", "ec2:CreateTags",
                        "iam:PassRole",
                        "cloudformation:CreateStack", "cloudformation:UpdateStack",
                        "cloudformation:DescribeStacks",
                        "iam:CreateAccessKey", "iam:UpdateAccessKey",
                        "iam:AttachUserPolicy", "iam:AttachRolePolicy",
                    ], "Resource": "*"},
                ],
            },
        },
    ]

    # ── Roles ───────────────────────────────────────────────────────────────
    roles = [
        {
            "RoleName": "ec2-instance-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/ec2-instance-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform"),
            "attached_policies": [{"PolicyName": "AmazonEC2RoleforSSM", "PolicyArn": "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"}],
            "inline_policies": [
                {
                    "PolicyName": "SSMRunCommandAccess",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{"Effect": "Allow", "Action": ["ssm:SendCommand", "ssm:GetCommandInvocation", "ec2:DescribeInstances"], "Resource": "*"}],
                    },
                },
            ],
        },
        {
            "RoleName": "lambda-exec-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/lambda-exec-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform"),
            "attached_policies": [{"PolicyName": "AWSLambdaBasicExecutionRole", "PolicyArn": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"}],
            # Inline policy grants lambda:CreateFunction + iam:PassRole — a classic escalation vector
            "inline_policies": [
                {
                    "PolicyName": "LambdaDeployAccess",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{"Effect": "Allow", "Action": [
                            "lambda:CreateFunction",
                            "lambda:UpdateFunctionCode",
                            "lambda:InvokeFunction",
                            "iam:PassRole",
                            "sts:AssumeRole",
                        ], "Resource": "*"}],
                    },
                },
            ],
        },
        {
            "RoleName": "ecs-task-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/ecs-task-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"Service": "ecs-tasks.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform"),
            "attached_policies": [{"PolicyName": "ECSTaskPolicy", "PolicyArn": ecs_policy_arn}],
            "inline_policies": [],
        },
        {
            "RoleName": "eks-cluster-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/eks-cluster-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"Service": "eks.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform"),
            "attached_policies": [{"PolicyName": "AmazonEKSClusterPolicy", "PolicyArn": "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"}],
            "inline_policies": [],
        },
        {
            "RoleName": "codepipeline-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/codepipeline-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"Service": "codepipeline.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform"),
            "attached_policies": [{"PolicyName": "AWSCodePipelineFullAccess", "PolicyArn": "arn:aws:iam::aws:policy/AWSCodePipelineFullAccess"}],
            "inline_policies": [],
        },
        {
            "RoleName": "rds-monitoring-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/rds-monitoring-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"Service": "monitoring.rds.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform"),
            "attached_policies": [{"PolicyName": "AmazonRDSEnhancedMonitoringRole", "PolicyArn": "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"}],
            "inline_policies": [],
        },
        {
            "RoleName": "glue-service-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/glue-service-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"Service": "glue.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform"),
            # AWSGlueServiceRole grants glue:*, s3:*, ec2:*, cloudwatch:*
            "attached_policies": [{"PolicyName": "AWSGlueServiceRole", "PolicyArn": "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"}],
            "inline_policies": [],
        },
        {
            "RoleName": "devops-infra-role",
            "RoleId": f"AROA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "role/devops-infra-role"),
            "AssumeRolePolicyDocument": {"Statement": [{"Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT_ID}:root"}, "Action": "sts:AssumeRole"}]},
            "Tags": tags("ManagedBy", "terraform", "Team", "devops"),
            "attached_policies": [{"PolicyName": "InfraMgmtPolicy", "PolicyArn": infra_policy_arn}],
            "inline_policies": [],
        },
    ]

    # ── Users ────────────────────────────────────────────────────────────────
    users = [
        {
            "UserName": "admin",
            "UserId": f"AIDA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "user/admin"),
            "mfa_devices": [{"SerialNumber": arnf("iam", "", "mfa/admin")}],
            "access_keys": [{"AccessKeyId": f"AKIA{_hex(16).upper()}", "Status": "Active"}],
            "attached_policies": [{"PolicyName": "AdministratorAccess", "PolicyArn": "arn:aws:iam::aws:policy/AdministratorAccess"}],
            "inline_policies": [],
        },
        {
            # ci-deploy has DeployPolicy which grants iam:CreatePolicyVersion + lambda:UpdateFunctionCode
            # → matches privilege escalation paths involving policy version creation and Lambda code update
            "UserName": "ci-deploy",
            "UserId": f"AIDA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "user/ci-deploy"),
            "mfa_devices": [],
            "access_keys": [{"AccessKeyId": f"AKIA{_hex(16).upper()}", "Status": "Active"}],
            "attached_policies": [{"PolicyName": "DeployPolicy", "PolicyArn": deploy_policy_arn}],
            "inline_policies": [
                {
                    # Additional inline: can create Lambda functions and pass roles
                    "PolicyName": "CIExtraAccess",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{"Effect": "Allow", "Action": [
                            "iam:PassRole",
                            "lambda:CreateFunction",
                            "lambda:AddPermission",
                            "ec2:RunInstances",
                        ], "Resource": "*"}],
                    },
                },
            ],
        },
        {
            "UserName": "readonly-auditor",
            "UserId": f"AIDA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "user/readonly-auditor"),
            "mfa_devices": [{"SerialNumber": arnf("iam", "", "mfa/readonly-auditor")}],
            "access_keys": [],
            "attached_policies": [{"PolicyName": "ReadOnlyAccess", "PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}],
            "inline_policies": [],
        },
        {
            # data-analyst has S3DataReadPolicy which grants glue:UpdateJob + iam:PassRole
            # → matches Glue-based iam:PassRole escalation path
            "UserName": "data-analyst",
            "UserId": f"AIDA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "user/data-analyst"),
            "mfa_devices": [{"SerialNumber": arnf("iam", "", "mfa/data-analyst")}],
            "access_keys": [],
            "attached_policies": [{"PolicyName": "S3DataReadPolicy", "PolicyArn": s3data_policy_arn}],
            "inline_policies": [],
        },
        {
            # devops-lead has iam:AttachUserPolicy + iam:CreateAccessKey via InfraMgmtPolicy
            # → matches principal-access escalation paths
            "UserName": "devops-lead",
            "UserId": f"AIDA{_hex(16).upper()}",
            "Arn": arnf("iam", "", "user/devops-lead"),
            "mfa_devices": [{"SerialNumber": arnf("iam", "", "mfa/devops-lead")}],
            "access_keys": [{"AccessKeyId": f"AKIA{_hex(16).upper()}", "Status": "Active"}],
            "attached_policies": [{"PolicyName": "InfraMgmtPolicy", "PolicyArn": infra_policy_arn}],
            "inline_policies": [
                {
                    "PolicyName": "DevOpsRoleAssume",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{"Effect": "Allow", "Action": ["sts:AssumeRole"], "Resource": "*"}],
                    },
                },
            ],
        },
    ]

    groups = [
        {"GroupName": "Developers", "GroupId": f"AGPA{_hex(16).upper()}", "Arn": arnf("iam", "", "group/Developers")},
        {"GroupName": "Ops",        "GroupId": f"AGPA{_hex(16).upper()}", "Arn": arnf("iam", "", "group/Ops")},
        {"GroupName": "ReadOnly",   "GroupId": f"AGPA{_hex(16).upper()}", "Arn": arnf("iam", "", "group/ReadOnly")},
        {"GroupName": "DataTeam",   "GroupId": f"AGPA{_hex(16).upper()}", "Arn": arnf("iam", "", "group/DataTeam")},
    ]
    return {
        "users": users,
        "roles": roles,
        "groups": groups,
        "policies": policies,
        "instance_profiles": [
            {"InstanceProfileName": "ec2-instance-profile", "InstanceProfileId": f"AIPA{_hex(16).upper()}", "Arn": arnf("iam", "", "instance-profile/ec2-instance-profile"), "Roles": [roles[0]]},
        ],
        "account_summary": {"Users": len(users), "Roles": len(roles), "Groups": len(groups), "Policies": len(policies), "MFADevices": 4},
        "account_aliases": ["acme-corp"],
    }


def build_s3() -> dict:
    buckets = []
    for name, env in [
        ("acme-prod-assets",      "prod"),
        ("acme-prod-logs",        "prod"),
        ("acme-prod-backups",     "prod"),
        ("acme-dev-artifacts",    "dev"),
        ("acme-cf-access-logs",   "prod"),
        ("acme-data-lake",        "prod"),
        ("acme-terraform-state",  "prod"),
    ]:
        encrypted = {"ServerSideEncryptionConfiguration": {"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}}
        buckets.append({
            "Name": name,
            "CreationDate": "2024-01-15T00:00:00Z",
            "encryption": encrypted,
            "versioning": {"Status": "Enabled"} if env == "prod" else {},
            "public_access_block": {"PublicAccessBlockConfiguration": {"BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True}},
            "logging": {"LoggingEnabled": {"TargetBucket": "acme-prod-logs", "TargetPrefix": f"{name}/"}} if name != "acme-prod-logs" else {},
            "tagging": tags("Environment", env, "Project", "acme", "ManagedBy", "terraform"),
            "policy": {},
            "lifecycle": [{"ID": "expire-old", "Status": "Enabled", "Expiration": {"Days": 365}}] if "backup" in name or "log" in name else [],
            "acl": {},
        })
    return {"buckets": buckets}


def build_route53() -> dict:
    zone_id = f"Z{_hex(10).upper()}"
    zone_id_internal = f"Z{_hex(10).upper()}"
    return {
        "hosted_zones": [
            {
                "Id": f"/hostedzone/{zone_id}",
                "Name": "acme-corp.com.",
                "Config": {"PrivateZone": False},
                "ResourceRecordSetCount": 8,
                "record_sets": [
                    {"Name": "acme-corp.com.",        "Type": "A",    "AliasTarget": {"DNSName": f"d{_hex(12)}.cloudfront.net", "EvaluateTargetHealth": False}},
                    {"Name": "www.acme-corp.com.",     "Type": "CNAME","TTL": 300,  "ResourceRecords": [{"Value": "acme-corp.com"}]},
                    {"Name": "api.acme-corp.com.",     "Type": "CNAME","TTL": 300,  "ResourceRecords": [{"Value": f"prod-alb-{_hex(8)}.us-east-1.elb.amazonaws.com"}]},
                    {"Name": "mail.acme-corp.com.",    "Type": "MX",   "TTL": 3600, "ResourceRecords": [{"Value": "10 aspmx.l.google.com"}]},
                    {"Name": "acme-corp.com.",         "Type": "TXT",  "TTL": 300,  "ResourceRecords": [{"Value": '"v=spf1 include:_spf.google.com ~all"'}]},
                    {"Name": "_dmarc.acme-corp.com.",  "Type": "TXT",  "TTL": 300,  "ResourceRecords": [{"Value": '"v=DMARC1; p=quarantine; rua=mailto:dmarc@acme-corp.com"'}]},
                    {"Name": "status.acme-corp.com.",  "Type": "CNAME","TTL": 300,  "ResourceRecords": [{"Value": "acme-corp.statuspage.io"}]},
                    {"Name": "docs.acme-corp.com.",    "Type": "CNAME","TTL": 300,  "ResourceRecords": [{"Value": "acme-corp.gitbook.io"}]},
                ],
            },
            {
                "Id": f"/hostedzone/{zone_id_internal}",
                "Name": "internal.acme-corp.com.",
                "Config": {"PrivateZone": True},
                "ResourceRecordSetCount": 3,
                "record_sets": [
                    {"Name": "db.internal.acme-corp.com.",    "Type": "CNAME", "TTL": 60, "ResourceRecords": [{"Value": f"prod-postgres-01.{_hex(8)}.us-east-1.rds.amazonaws.com"}]},
                    {"Name": "redis.internal.acme-corp.com.", "Type": "CNAME", "TTL": 60, "ResourceRecords": [{"Value": f"prod-redis-rg.abc123.ng.0001.use1.cache.amazonaws.com"}]},
                    {"Name": "kafka.internal.acme-corp.com.", "Type": "CNAME", "TTL": 60, "ResourceRecords": [{"Value": f"b-1.prod-kafka.{_hex(8)}.c1.kafka.us-east-1.amazonaws.com"}]},
                ],
            },
        ]
    }


def build_cloudfront() -> dict:
    cf_id = f"E{_hex(10).upper()}"
    cf_id2 = f"E{_hex(10).upper()}"
    return {
        "distributions": [
            {
                "Id": cf_id,
                "DomainName": f"d{_hex(12)}.cloudfront.net",
                "Status": "Deployed",
                "Origins": {"Items": [
                    {"Id": "S3-acme-prod-assets", "DomainName": "acme-prod-assets.s3.amazonaws.com"},
                ]},
                "DefaultCacheBehavior": {"ViewerProtocolPolicy": "redirect-to-https", "CachePolicyId": _hex(36)},
                "HttpVersion": "http2",
                "PriceClass": "PriceClass_100",
                "Tags": {"Items": [tag("Environment", "prod")]},
            },
            {
                "Id": cf_id2,
                "DomainName": f"d{_hex(12)}.cloudfront.net",
                "Status": "Deployed",
                "Origins": {"Items": [
                    {"Id": "ALB-api", "DomainName": f"prod-alb-{_hex(8)}.us-east-1.elb.amazonaws.com"},
                ]},
                "DefaultCacheBehavior": {"ViewerProtocolPolicy": "https-only"},
                "HttpVersion": "http2and3",
                "PriceClass": "PriceClass_All",
                "Tags": {"Items": [tag("Environment", "prod"), tag("Purpose", "api")]},
            },
        ]
    }


def build_organizations() -> dict:
    return {
        "organization": {
            "Id": f"o-{_hex(10)}",
            "MasterAccountId": ACCOUNT_ID,
            "FeatureSet": "ALL",
            "MasterAccountEmail": "aws-root@acme-corp.com",
        },
        "accounts": [
            {"Id": ACCOUNT_ID,    "Name": "acme-prod",    "Status": "ACTIVE", "Email": "aws-prod@acme-corp.com"},
            {"Id": "234567890123", "Name": "acme-dev",     "Status": "ACTIVE", "Email": "aws-dev@acme-corp.com"},
            {"Id": "345678901234", "Name": "acme-staging", "Status": "ACTIVE", "Email": "aws-staging@acme-corp.com"},
        ],
    }


# ---------------------------------------------------------------------------
# Regional builder
# ---------------------------------------------------------------------------

class RegionBuilder:
    """Builds all regional service data for one region.

    All resource IDs are created in __init__ so they can be
    cross-referenced consistently across every service's output.
    """

    def __init__(self, region: str, cidr_prefix: str, env: str = "prod"):
        self.region = region
        self.env = env
        self.az_a = f"{region}a"
        self.az_b = f"{region}b"

        # VPCs
        self.vpc_main = ec2id("vpc")
        self.vpc_data = ec2id("vpc")

        # Subnets in main VPC
        self.sub_pub_a  = ec2id("subnet")
        self.sub_pub_b  = ec2id("subnet")
        self.sub_priv_a = ec2id("subnet")
        self.sub_priv_b = ec2id("subnet")

        # Subnets in data VPC
        self.sub_data_a = ec2id("subnet")
        self.sub_data_b = ec2id("subnet")

        # Security groups
        self.sg_alb     = ec2id("sg")
        self.sg_app     = ec2id("sg")
        self.sg_db      = ec2id("sg")
        self.sg_cache   = ec2id("sg")
        self.sg_lambda  = ec2id("sg")
        self.sg_bastion = ec2id("sg")
        self.sg_eks     = ec2id("sg")

        # Gateways
        self.igw = ec2id("igw")
        self.nat = ec2id("nat")

        # KMS key (used across RDS, EBS, S3, ElastiCache, etc.)
        self.kms_key_id = _hex(8)
        self.kms_key_arn = arnf("kms", region, f"key/{self.kms_key_id}")

        # ALB
        self.alb_arn = arnf("elasticloadbalancing", region, f"loadbalancer/app/{env}-alb/{_hex(16)}")
        self.alb_dns = f"{env}-alb-{_hex(8)}.{region}.elb.amazonaws.com"

        # Cluster names
        self.ecs_cluster_name = f"{env}-cluster"
        self.ecs_cluster_arn  = arnf("ecs", region, f"cluster/{env}-cluster")
        self.eks_cluster_name = f"{env}-eks"

        self.cidr = cidr_prefix

    # ------------------------------------------------------------------ ec2
    def ec2(self) -> dict:
        instances = []

        # Bastion
        bastion_id = ec2id("i")
        instances.append({"Instances": [{
            "InstanceId": bastion_id, "InstanceType": "t3.nano",
            "State": {"Name": "running"},
            "Tags": tags("Name", f"bastion-{self.env}", "Environment", self.env, "Role", "bastion"),
            "VpcId": self.vpc_main, "SubnetId": self.sub_pub_a,
            "SecurityGroups": [{"GroupId": self.sg_bastion, "GroupName": "bastion-sg"}],
            "PrivateIpAddress": f"{self.cidr}.1.5",
            "PublicIpAddress": f"54.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            "KeyName": f"{self.env}-keypair",
        }]})

        # App servers
        for i in range(1, 4):
            iid = ec2id("i")
            subnet = self.sub_priv_a if i % 2 == 1 else self.sub_priv_b
            instances.append({"Instances": [{
                "InstanceId": iid, "InstanceType": "t3.medium",
                "State": {"Name": "running"},
                "Tags": tags("Name", f"app-server-{i}", "Environment", self.env, "Role", "app"),
                "VpcId": self.vpc_main, "SubnetId": subnet,
                "SecurityGroups": [{"GroupId": self.sg_app, "GroupName": "app-sg"}],
                "PrivateIpAddress": f"{self.cidr}.3.{10 + i}",
                "IamInstanceProfile": {"Arn": arnf("iam", "", "instance-profile/ec2-instance-profile")},
                "KeyName": f"{self.env}-keypair",
            }]})

        # Data processor
        instances.append({"Instances": [{
            "InstanceId": ec2id("i"), "InstanceType": "c5.2xlarge",
            "State": {"Name": "running"},
            "Tags": tags("Name", "data-processor-1", "Environment", self.env, "Role", "processing"),
            "VpcId": self.vpc_data, "SubnetId": self.sub_data_a,
            "SecurityGroups": [{"GroupId": self.sg_db, "GroupName": "data-sg"}],
            "PrivateIpAddress": f"{self.cidr}.10.20",
            "KeyName": f"{self.env}-keypair",
        }]})

        # Stopped instance
        instances.append({"Instances": [{
            "InstanceId": ec2id("i"), "InstanceType": "t3.small",
            "State": {"Name": "stopped"},
            "Tags": tags("Name", "old-worker", "Environment", self.env),
            "VpcId": self.vpc_main, "SubnetId": self.sub_priv_a,
            "SecurityGroups": [{"GroupId": self.sg_app, "GroupName": "app-sg"}],
            "PrivateIpAddress": f"{self.cidr}.3.50",
        }]})

        vpcs = [
            {"VpcId": self.vpc_main, "CidrBlock": f"{self.cidr}.0.0/16",  "Tags": tags("Name", f"{self.env}-main-vpc", "Environment", self.env), "State": "available", "IsDefault": False},
            {"VpcId": self.vpc_data, "CidrBlock": f"{self.cidr}.10.0/20", "Tags": tags("Name", f"{self.env}-data-vpc", "Environment", self.env), "State": "available", "IsDefault": False},
        ]

        subnets = [
            {"SubnetId": self.sub_pub_a,  "VpcId": self.vpc_main, "CidrBlock": f"{self.cidr}.1.0/24",   "AvailabilityZone": self.az_a, "Tags": tags("Name", "public-a",  "Environment", self.env), "MapPublicIpOnLaunch": True},
            {"SubnetId": self.sub_pub_b,  "VpcId": self.vpc_main, "CidrBlock": f"{self.cidr}.2.0/24",   "AvailabilityZone": self.az_b, "Tags": tags("Name", "public-b",  "Environment", self.env), "MapPublicIpOnLaunch": True},
            {"SubnetId": self.sub_priv_a, "VpcId": self.vpc_main, "CidrBlock": f"{self.cidr}.3.0/24",   "AvailabilityZone": self.az_a, "Tags": tags("Name", "private-a", "Environment", self.env), "MapPublicIpOnLaunch": False},
            {"SubnetId": self.sub_priv_b, "VpcId": self.vpc_main, "CidrBlock": f"{self.cidr}.4.0/24",   "AvailabilityZone": self.az_b, "Tags": tags("Name", "private-b", "Environment", self.env), "MapPublicIpOnLaunch": False},
            {"SubnetId": self.sub_data_a, "VpcId": self.vpc_data, "CidrBlock": f"{self.cidr}.10.0/25",  "AvailabilityZone": self.az_a, "Tags": tags("Name", "data-a",    "Environment", self.env), "MapPublicIpOnLaunch": False},
            {"SubnetId": self.sub_data_b, "VpcId": self.vpc_data, "CidrBlock": f"{self.cidr}.10.128/25","AvailabilityZone": self.az_b, "Tags": tags("Name", "data-b",    "Environment", self.env), "MapPublicIpOnLaunch": False},
        ]

        security_groups = [
            {
                "GroupId": self.sg_alb, "GroupName": "alb-sg", "VpcId": self.vpc_main,
                "Description": "ALB security group",
                "Tags": tags("Name", "alb-sg"),
                "IpPermissions": [
                    {"FromPort": 80,  "ToPort": 80,  "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                    {"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                ],
                "IpPermissionsEgress": [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            },
            {
                "GroupId": self.sg_app, "GroupName": "app-sg", "VpcId": self.vpc_main,
                "Description": "App server security group",
                "Tags": tags("Name", "app-sg"),
                "IpPermissions": [
                    {"FromPort": 8080, "ToPort": 8080, "IpProtocol": "tcp", "UserIdGroupPairs": [{"GroupId": self.sg_alb, "UserId": ACCOUNT_ID}]},
                    {"FromPort": 22,   "ToPort": 22,   "IpProtocol": "tcp", "UserIdGroupPairs": [{"GroupId": self.sg_bastion, "UserId": ACCOUNT_ID}]},
                ],
                "IpPermissionsEgress": [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            },
            {
                "GroupId": self.sg_db, "GroupName": "db-sg", "VpcId": self.vpc_main,
                "Description": "Database security group",
                "Tags": tags("Name", "db-sg"),
                "IpPermissions": [
                    {"FromPort": 5432, "ToPort": 5432, "IpProtocol": "tcp", "UserIdGroupPairs": [{"GroupId": self.sg_app, "UserId": ACCOUNT_ID}]},
                    {"FromPort": 3306, "ToPort": 3306, "IpProtocol": "tcp", "UserIdGroupPairs": [{"GroupId": self.sg_app, "UserId": ACCOUNT_ID}]},
                ],
                "IpPermissionsEgress": [],
            },
            {
                "GroupId": self.sg_cache, "GroupName": "cache-sg", "VpcId": self.vpc_main,
                "Description": "ElastiCache security group",
                "Tags": tags("Name", "cache-sg"),
                "IpPermissions": [
                    {"FromPort": 6379, "ToPort": 6379, "IpProtocol": "tcp", "UserIdGroupPairs": [{"GroupId": self.sg_app, "UserId": ACCOUNT_ID}]},
                    {"FromPort": 6379, "ToPort": 6379, "IpProtocol": "tcp", "UserIdGroupPairs": [{"GroupId": self.sg_lambda, "UserId": ACCOUNT_ID}]},
                ],
                "IpPermissionsEgress": [],
            },
            {
                "GroupId": self.sg_lambda, "GroupName": "lambda-sg", "VpcId": self.vpc_main,
                "Description": "Lambda VPC security group",
                "Tags": tags("Name", "lambda-sg"),
                "IpPermissions": [],
                "IpPermissionsEgress": [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            },
            {
                "GroupId": self.sg_bastion, "GroupName": "bastion-sg", "VpcId": self.vpc_main,
                "Description": "Bastion SSH access",
                "Tags": tags("Name", "bastion-sg"),
                "IpPermissions": [{"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "203.0.113.0/24", "Description": "Corporate VPN"}]}],
                "IpPermissionsEgress": [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            },
            {
                "GroupId": self.sg_eks, "GroupName": "eks-cluster-sg", "VpcId": self.vpc_main,
                "Description": "EKS cluster security group",
                "Tags": tags("Name", "eks-cluster-sg"),
                "IpPermissions": [
                    {"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp", "UserIdGroupPairs": [{"GroupId": self.sg_app, "UserId": ACCOUNT_ID}]},
                ],
                "IpPermissionsEgress": [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            },
        ]

        eips = [
            {"PublicIp": f"52.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}", "AllocationId": ec2id("eipalloc"), "Domain": "vpc", "Tags": tags("Name", "nat-eip", "Environment", self.env)},
        ]

        volumes = []
        for vname, sz, iid in [
            ("bastion-root", 20, bastion_id),
            ("app-1-root", 100, None), ("app-2-root", 100, None), ("app-3-root", 100, None),
            ("data-proc-root", 50, None), ("data-proc-data", 1000, None),
        ]:
            v = {
                "VolumeId": ec2id("vol"), "Size": sz, "State": "in-use",
                "Encrypted": True, "KmsKeyId": self.kms_key_arn,
                "AvailabilityZone": self.az_a,
                "VolumeType": "gp3",
                "Tags": tags("Name", vname, "Environment", self.env),
            }
            if iid:
                v["Attachments"] = [{"InstanceId": iid, "Device": "/dev/xvda", "State": "attached"}]
            volumes.append(v)

        return {
            "instances": instances,
            "vpcs": vpcs,
            "subnets": subnets,
            "security_groups": security_groups,
            "internet_gateways": [{"InternetGatewayId": self.igw, "Attachments": [{"VpcId": self.vpc_main, "State": "attached"}], "Tags": tags("Name", f"{self.env}-igw")}],
            "nat_gateways": [{"NatGatewayId": self.nat, "VpcId": self.vpc_main, "SubnetId": self.sub_pub_a, "State": "available", "ConnectivityType": "public", "Tags": tags("Name", f"{self.env}-nat")}],
            "elastic_ips": eips,
            "volumes": volumes,
            "key_pairs": [{"KeyName": f"{self.env}-keypair", "KeyPairId": ec2id("key-pair"), "Tags": tags("Environment", self.env)}],
            "snapshots": [],
            "amis": [],
            "network_interfaces": [],
            "route_tables": [
                {"RouteTableId": ec2id("rtb"), "VpcId": self.vpc_main, "Tags": tags("Name", "public-rt"),  "Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": self.igw, "State": "active"}]},
                {"RouteTableId": ec2id("rtb"), "VpcId": self.vpc_main, "Tags": tags("Name", "private-rt"), "Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "NatGatewayId": self.nat, "State": "active"}]},
            ],
            "vpc_endpoints": [
                {"VpcEndpointId": ec2id("vpce"), "VpcEndpointType": "Interface", "VpcId": self.vpc_main, "ServiceName": f"com.amazonaws.{self.region}.s3", "State": "available"},
                {"VpcEndpointId": ec2id("vpce"), "VpcEndpointType": "Interface", "VpcId": self.vpc_main, "ServiceName": f"com.amazonaws.{self.region}.secretsmanager", "State": "available"},
            ],
            "vpc_peering_connections": [],
            "transit_gateways": [],
            "launch_templates": [{"LaunchTemplateId": ec2id("lt"), "LaunchTemplateName": f"{self.env}-app-lt", "DefaultVersionNumber": 3, "LatestVersionNumber": 3, "Tags": tags("Environment", self.env)}],
            "placement_groups": [],
            "flow_logs": [{"FlowLogId": ec2id("fl"), "ResourceId": self.vpc_main, "TrafficType": "ALL", "LogDestinationType": "cloud-watch-logs", "LogGroupName": f"/aws/vpc/flowlogs/{self.env}", "DeliverLogsStatus": "SUCCESS"}],
            "network_acls": [
                {"NetworkAclId": ec2id("acl"), "VpcId": self.vpc_main, "IsDefault": True,  "Tags": tags("Name", f"{self.env}-default-acl")},
                {"NetworkAclId": ec2id("acl"), "VpcId": self.vpc_main, "IsDefault": False, "Tags": tags("Name", f"{self.env}-db-acl")},
            ],
            "vpn_connections": [],
            "vpn_gateways": [],
            "customer_gateways": [],
            "transit_gateway_attachments": [],
            "dhcp_options": [{"DhcpOptionsId": ec2id("dopt"), "DhcpConfigurations": [{"Key": "domain-name-servers", "Values": [{"Value": "AmazonProvidedDNS"}]}], "Tags": tags("Name", f"{self.env}-dhcp")}],
        }

    # ------------------------------------------------------------------ rds
    def rds(self) -> dict:
        subnet_grp = f"{self.env}-db-subnet-group"
        pg_id      = f"{self.env}-postgres-01"
        mysql_id   = f"{self.env}-mysql-01"
        aurora_id  = f"{self.env}-aurora-cluster"

        return {
            "db_instances": [
                {
                    "DBInstanceIdentifier": pg_id,
                    "DBInstanceClass": "db.r6g.large", "Engine": "postgres", "EngineVersion": "15.4",
                    "DBInstanceStatus": "available",
                    "Endpoint": {"Address": f"{pg_id}.{_hex(8)}.{self.region}.rds.amazonaws.com", "Port": 5432},
                    "VpcSecurityGroups": [{"VpcSecurityGroupId": self.sg_db, "Status": "active"}],
                    "DBSubnetGroup": {"DBSubnetGroupName": subnet_grp, "VpcId": self.vpc_main},
                    "MultiAZ": True, "StorageEncrypted": True, "AllocatedStorage": 200,
                    "Tags": tags("Name", pg_id, "Environment", self.env),
                },
                {
                    "DBInstanceIdentifier": mysql_id,
                    "DBInstanceClass": "db.t3.medium", "Engine": "mysql", "EngineVersion": "8.0.35",
                    "DBInstanceStatus": "available",
                    "Endpoint": {"Address": f"{mysql_id}.{_hex(8)}.{self.region}.rds.amazonaws.com", "Port": 3306},
                    "VpcSecurityGroups": [{"VpcSecurityGroupId": self.sg_db, "Status": "active"}],
                    "DBSubnetGroup": {"DBSubnetGroupName": subnet_grp, "VpcId": self.vpc_main},
                    "MultiAZ": False, "StorageEncrypted": True, "AllocatedStorage": 100,
                    "Tags": tags("Name", mysql_id, "Environment", self.env),
                },
                {
                    "DBInstanceIdentifier": f"{aurora_id}-instance-1",
                    "DBInstanceClass": "db.r6g.large", "Engine": "aurora-postgresql", "EngineVersion": "15.4",
                    "DBInstanceStatus": "available",
                    "DBClusterIdentifier": aurora_id,
                    "Endpoint": {"Address": f"{aurora_id}-instance-1.{_hex(8)}.{self.region}.rds.amazonaws.com", "Port": 5432},
                    "VpcSecurityGroups": [{"VpcSecurityGroupId": self.sg_db, "Status": "active"}],
                    "DBSubnetGroup": {"DBSubnetGroupName": subnet_grp, "VpcId": self.vpc_main},
                    "MultiAZ": True, "StorageEncrypted": True, "AllocatedStorage": 1,
                    "Tags": tags("Name", f"{aurora_id}-instance-1", "Environment", self.env),
                },
            ],
            "db_clusters": [{
                "DBClusterIdentifier": aurora_id,
                "Engine": "aurora-postgresql", "EngineVersion": "15.4", "Status": "available",
                "Endpoint": f"{aurora_id}.cluster-{_hex(8)}.{self.region}.rds.amazonaws.com",
                "ReaderEndpoint": f"{aurora_id}.cluster-ro-{_hex(8)}.{self.region}.rds.amazonaws.com",
                "Port": 5432,
                "VpcSecurityGroups": [{"VpcSecurityGroupId": self.sg_db}],
                "DBSubnetGroup": subnet_grp,
                "StorageEncrypted": True,
                "Tags": tags("Name", aurora_id, "Environment", self.env),
            }],
            "db_snapshots": [
                {"DBSnapshotIdentifier": f"{pg_id}-snap-20260101", "DBInstanceIdentifier": pg_id, "SnapshotType": "automated", "Status": "available", "Engine": "postgres"},
            ],
            "db_subnet_groups": [{
                "DBSubnetGroupName": subnet_grp,
                "VpcId": self.vpc_main,
                "Subnets": [
                    {"SubnetIdentifier": self.sub_priv_a, "SubnetAvailabilityZone": {"Name": self.az_a}},
                    {"SubnetIdentifier": self.sub_priv_b, "SubnetAvailabilityZone": {"Name": self.az_b}},
                ],
            }],
        }

    # ---------------------------------------------------------------- lambda
    def lambda_(self) -> dict:
        funcs = []
        specs = [
            ("api-handler",       "python3.12", "api",         True),
            ("event-processor",   "python3.12", "processing",  True),
            ("scheduled-cleanup", "nodejs20.x",  "maintenance", False),
            ("auth-authorizer",   "python3.12", "auth",        True),
            ("image-resizer",     "python3.12", "media",       False),
            ("data-transformer",  "java17",      "etl",         False),
        ]
        for name, runtime, purpose, in_vpc in specs:
            fn_arn = arnf("lambda", self.region, f"function:{name}")
            funcs.append({
                "FunctionName": name,
                "FunctionArn": fn_arn,
                "Runtime": runtime,
                "Role": arnf("iam", "", "role/lambda-exec-role"),
                "Handler": "index.handler",
                "CodeSize": random.randint(50_000, 50_000_000),
                "Timeout": random.choice([30, 60, 300]),
                "MemorySize": random.choice([128, 256, 512, 1024]),
                "LastModified": "2026-01-15T10:00:00.000+0000",
                "VpcConfig": {
                    "VpcId": self.vpc_main,
                    "SubnetIds": [self.sub_priv_a, self.sub_priv_b],
                    "SecurityGroupIds": [self.sg_lambda],
                } if in_vpc else {},
                "Environment": {"Variables": {"ENV": self.env, "REGION": self.region}},
                "Tags": {"Environment": self.env, "Purpose": purpose},
                "policy": {},
                "event_source_mappings": [
                    {"EventSourceArn": arnf("sqs", self.region, f"{self.env}-task-queue"), "FunctionArn": fn_arn, "State": "Enabled", "BatchSize": 10}
                ] if purpose == "processing" else [],
            })
        return {"functions": funcs}

    # ------------------------------------------------------------------- ecs
    def ecs(self) -> dict:
        api_svc_arn    = arnf("ecs", self.region, f"service/{self.ecs_cluster_name}/api-service")
        worker_svc_arn = arnf("ecs", self.region, f"service/{self.ecs_cluster_name}/worker-service")
        tg_arn         = arnf("elasticloadbalancing", self.region, f"targetgroup/api-tg/{_hex(16)}")
        return {
            "clusters": [{
                "clusterArn": self.ecs_cluster_arn,
                "clusterName": self.ecs_cluster_name,
                "status": "ACTIVE",
                "registeredContainerInstancesCount": 0,
                "runningTasksCount": 5, "pendingTasksCount": 0,
                "tags": tags("Environment", self.env),
                "services": [
                    {
                        "serviceName": "api-service", "serviceArn": api_svc_arn,
                        "clusterArn": self.ecs_cluster_arn, "status": "ACTIVE",
                        "desiredCount": 3, "runningCount": 3, "pendingCount": 0,
                        "launchType": "FARGATE",
                        "networkConfiguration": {"awsvpcConfiguration": {"subnets": [self.sub_priv_a, self.sub_priv_b], "securityGroups": [self.sg_app], "assignPublicIp": "DISABLED"}},
                        "loadBalancers": [{"targetGroupArn": tg_arn, "containerName": "api", "containerPort": 8080}],
                        "tags": tags("Environment", self.env),
                    },
                    {
                        "serviceName": "worker-service", "serviceArn": worker_svc_arn,
                        "clusterArn": self.ecs_cluster_arn, "status": "ACTIVE",
                        "desiredCount": 2, "runningCount": 2, "pendingCount": 0,
                        "launchType": "FARGATE",
                        "networkConfiguration": {"awsvpcConfiguration": {"subnets": [self.sub_priv_a], "securityGroups": [self.sg_app], "assignPublicIp": "DISABLED"}},
                        "tags": tags("Environment", self.env),
                    },
                ],
            }],
            "task_definition_arns": [
                arnf("ecs", self.region, "task-definition/api-task:12"),
                arnf("ecs", self.region, "task-definition/worker-task:8"),
            ],
        }

    # ------------------------------------------------------------------- eks
    def eks(self) -> dict:
        return {
            "clusters": [{
                "name": self.eks_cluster_name,
                "arn": arnf("eks", self.region, f"cluster/{self.eks_cluster_name}"),
                "status": "ACTIVE", "version": "1.29",
                "endpoint": f"https://{_hex(32)}.gr7.{self.region}.eks.amazonaws.com",
                "roleArn": arnf("iam", "", "role/eks-cluster-role"),
                "resourcesVpcConfig": {
                    "subnetIds": [self.sub_priv_a, self.sub_priv_b, self.sub_pub_a, self.sub_pub_b],
                    "securityGroupIds": [self.sg_eks],
                    "vpcId": self.vpc_main,
                    "endpointPublicAccess": False, "endpointPrivateAccess": True,
                },
                "tags": {"Environment": self.env},
            }]
        }

    # ------------------------------------------------------------------- elb
    def elb(self) -> dict:
        tg_api = arnf("elasticloadbalancing", self.region, f"targetgroup/api-tg/{_hex(16)}")
        tg_web = arnf("elasticloadbalancing", self.region, f"targetgroup/web-tg/{_hex(16)}")
        return {
            "load_balancers_v2": [{
                "LoadBalancerArn": self.alb_arn,
                "LoadBalancerName": f"{self.env}-alb",
                "DNSName": self.alb_dns,
                "Type": "application", "Scheme": "internet-facing",
                "VpcId": self.vpc_main,
                "SecurityGroups": [self.sg_alb],
                "AvailabilityZones": [
                    {"SubnetId": self.sub_pub_a, "ZoneName": self.az_a},
                    {"SubnetId": self.sub_pub_b, "ZoneName": self.az_b},
                ],
                "State": {"Code": "active"},
                "Tags": tags("Environment", self.env),
            }],
            "target_groups": [
                {"TargetGroupArn": tg_api, "TargetGroupName": "api-tg", "Protocol": "HTTP", "Port": 8080, "VpcId": self.vpc_main, "TargetType": "ip", "LoadBalancerArns": [self.alb_arn]},
                {"TargetGroupArn": tg_web, "TargetGroupName": "web-tg", "Protocol": "HTTP", "Port": 80,   "VpcId": self.vpc_main, "TargetType": "ip", "LoadBalancerArns": [self.alb_arn]},
            ],
            "classic_load_balancers": [],
        }

    # ------------------------------------------------------------ autoscaling
    def autoscaling(self) -> dict:
        asg_name = f"{self.env}-app-asg"
        return {
            "auto_scaling_groups": [{
                "AutoScalingGroupName": asg_name,
                "AutoScalingGroupARN": arnf("autoscaling", self.region, f"autoScalingGroup::AutoScalingGroupName/{asg_name}"),
                "LaunchTemplate": {"LaunchTemplateName": f"{self.env}-app-lt", "Version": "$Latest"},
                "MinSize": 2, "MaxSize": 10, "DesiredCapacity": 3,
                "AvailabilityZones": [self.az_a, self.az_b],
                "VPCZoneIdentifier": f"{self.sub_priv_a},{self.sub_priv_b}",
                "HealthCheckType": "ELB",
                "Tags": [{"Key": "Name", "Value": asg_name}, {"Key": "Environment", "Value": self.env}],
            }],
            "launch_configurations": [],
        }

    # --------------------------------------------------------------- dynamodb
    def dynamodb(self) -> dict:
        tables = []
        for tname in ["users", "sessions", "events", "feature-flags", "audit-log"]:
            full = f"{self.env}-{tname}"
            tables.append({
                "TableName": full,
                "TableArn": arnf("dynamodb", self.region, f"table/{full}"),
                "TableStatus": "ACTIVE",
                "TableSizeBytes": random.randint(1024, 100 * 1024 * 1024),
                "ItemCount": random.randint(100, 1_000_000),
                "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
                "SSEDescription": {"Status": "ENABLED", "SSEType": "KMS", "KMSMasterKeyArn": self.kms_key_arn},
                "Tags": tags("Environment", self.env),
            })
        return {"tables": tables}

    # ------------------------------------------------------------------- sqs
    def sqs(self) -> dict:
        queues = []
        for qname in ["task-queue", "task-queue-dlq", "notification-queue"]:
            url = f"https://sqs.{self.region}.amazonaws.com/{ACCOUNT_ID}/{self.env}-{qname}"
            queues.append({
                "url": url,
                "attributes": {
                    "QueueArn": arnf("sqs", self.region, f"{self.env}-{qname}"),
                    "ApproximateNumberOfMessages": str(random.randint(0, 500)),
                    "VisibilityTimeout": "30",
                    "MessageRetentionPeriod": "1209600",
                    "ReceiveMessageWaitTimeSeconds": "20",
                    "KmsMasterKeyId": self.kms_key_id,
                },
            })
        return {"queues": queues}

    # ------------------------------------------------------------------- sns
    def sns(self) -> dict:
        topics = []
        for tname in ["alerts", "deployments", "user-notifications"]:
            t_arn = arnf("sns", self.region, f"{self.env}-{tname}")
            topics.append({
                "TopicArn": t_arn,
                "attributes": {
                    "TopicArn": t_arn,
                    "DisplayName": f"{self.env} {tname.replace('-', ' ').title()}",
                    "KmsMasterKeyId": self.kms_key_id,
                },
                "subscriptions": [
                    {"SubscriptionArn": f"{t_arn}:{_hex(8)}", "Protocol": "email", "Endpoint": "ops@acme-corp.com"},
                    {"SubscriptionArn": f"{t_arn}:{_hex(8)}", "Protocol": "sqs",   "Endpoint": arnf("sqs", self.region, f"{self.env}-task-queue")},
                ],
            })
        return {"topics": topics}

    # -------------------------------------------------------------- cloudwatch
    def cloudwatch(self) -> dict:
        alarms = [
            {"AlarmName": "HighCPU-app",          "MetricName": "CPUUtilization",      "Namespace": "AWS/EC2",                "Threshold": 80,  "StateValue": "OK",    "ComparisonOperator": "GreaterThanThreshold"},
            {"AlarmName": "RDS-connections",       "MetricName": "DatabaseConnections", "Namespace": "AWS/RDS",                "Threshold": 100, "StateValue": "OK",    "ComparisonOperator": "GreaterThanThreshold"},
            {"AlarmName": "Lambda-errors",         "MetricName": "Errors",              "Namespace": "AWS/Lambda",             "Threshold": 10,  "StateValue": "OK",    "ComparisonOperator": "GreaterThanThreshold"},
            {"AlarmName": "ALB-5xx-rate",          "MetricName": "HTTPCode_ELB_5XX_Count","Namespace": "AWS/ApplicationELB",  "Threshold": 20,  "StateValue": "ALARM", "ComparisonOperator": "GreaterThanThreshold"},
            {"AlarmName": "SQS-queue-depth",       "MetricName": "ApproximateNumberOfMessagesVisible","Namespace": "AWS/SQS","Threshold": 1000,"StateValue": "OK",    "ComparisonOperator": "GreaterThanThreshold"},
            {"AlarmName": "Redis-memory",          "MetricName": "DatabaseMemoryUsagePercentage","Namespace": "AWS/ElastiCache","Threshold": 80, "StateValue": "OK",   "ComparisonOperator": "GreaterThanThreshold"},
        ]
        return {
            "alarms": alarms,
            "dashboards": [
                {"DashboardName": f"{self.env}-overview"},
                {"DashboardName": f"{self.env}-data-pipeline"},
            ],
        }

    # --------------------------------------------------------- cloudwatch_logs
    def cloudwatch_logs(self) -> dict:
        return {"log_groups": [
            {"logGroupName": "/aws/lambda/api-handler",                          "retentionInDays": 30},
            {"logGroupName": "/aws/lambda/event-processor",                      "retentionInDays": 30},
            {"logGroupName": "/aws/lambda/auth-authorizer",                      "retentionInDays": 30},
            {"logGroupName": f"/ecs/{self.ecs_cluster_name}",                    "retentionInDays": 90},
            {"logGroupName": f"/aws/eks/{self.eks_cluster_name}/cluster",        "retentionInDays": 90},
            {"logGroupName": f"/aws/rds/instance/{self.env}-postgres-01/postgresql", "retentionInDays": 30},
            {"logGroupName": f"/aws/vpc/flowlogs/{self.env}",                    "retentionInDays": 90},
            {"logGroupName": f"/aws/codebuild/api-build",                        "retentionInDays": 14},
        ]}

    # ---------------------------------------------------------- cloudformation
    def cloudformation(self) -> dict:
        stacks = []
        for sname in ["acme-network", "acme-app", "acme-data", "acme-monitoring", "acme-iam"]:
            stacks.append({
                "StackName": sname,
                "StackId": arnf("cloudformation", self.region, f"stack/{sname}/{_hex(36)}"),
                "StackStatus": "UPDATE_COMPLETE",
                "CreationTime": "2025-01-01T00:00:00Z",
                "LastUpdatedTime": "2026-01-15T00:00:00Z",
                "Tags": tags("Project", "acme", "Environment", self.env, "ManagedBy", "terraform"),
            })
        return {"stacks": stacks}

    # ------------------------------------------------------- secrets_manager
    def secrets_manager(self) -> dict:
        return {"secrets": [
            {"Name": f"{self.env}/db/postgres-password", "ARN": arnf("secretsmanager", self.region, f"secret:{self.env}/db/postgres-password-{_hex(6)}")},
            {"Name": f"{self.env}/db/mysql-password",    "ARN": arnf("secretsmanager", self.region, f"secret:{self.env}/db/mysql-password-{_hex(6)}")},
            {"Name": f"{self.env}/api/stripe-key",       "ARN": arnf("secretsmanager", self.region, f"secret:{self.env}/api/stripe-key-{_hex(6)}")},
            {"Name": f"{self.env}/api/jwt-secret",       "ARN": arnf("secretsmanager", self.region, f"secret:{self.env}/api/jwt-secret-{_hex(6)}")},
            {"Name": f"{self.env}/kafka/sasl-password",  "ARN": arnf("secretsmanager", self.region, f"secret:{self.env}/kafka/sasl-password-{_hex(6)}")},
        ]}

    # --------------------------------------------------------------------- ssm
    def ssm(self) -> dict:
        return {"parameters": [
            {"Name": f"/{self.env}/app/db-host",       "Type": "String",       "LastModifiedDate": "2026-01-01T00:00:00Z"},
            {"Name": f"/{self.env}/app/db-name",       "Type": "String",       "LastModifiedDate": "2026-01-01T00:00:00Z"},
            {"Name": f"/{self.env}/app/redis-host",    "Type": "String",       "LastModifiedDate": "2026-01-01T00:00:00Z"},
            {"Name": f"/{self.env}/app/feature-flags", "Type": "String",       "LastModifiedDate": "2026-01-15T00:00:00Z"},
            {"Name": f"/{self.env}/keys/internal-api", "Type": "SecureString", "LastModifiedDate": "2026-01-01T00:00:00Z"},
            {"Name": f"/{self.env}/kafka/broker-list", "Type": "String",       "LastModifiedDate": "2025-12-01T00:00:00Z"},
        ]}

    # --------------------------------------------------------------------- kms
    def kms(self) -> dict:
        return {"keys": [
            {"KeyId": self.kms_key_id, "Arn": self.kms_key_arn, "Description": f"{self.env} master encryption key", "KeyState": "Enabled", "KeyUsage": "ENCRYPT_DECRYPT", "KeySpec": "SYMMETRIC_DEFAULT", "Origin": "AWS_KMS", "MultiRegion": False},
            {"KeyId": _hex(8), "Arn": arnf("kms", self.region, f"key/{_hex(8)}"), "Description": "RDS encryption key",           "KeyState": "Enabled", "KeyUsage": "ENCRYPT_DECRYPT", "KeySpec": "SYMMETRIC_DEFAULT"},
            {"KeyId": _hex(8), "Arn": arnf("kms", self.region, f"key/{_hex(8)}"), "Description": "S3 data lake encryption key",  "KeyState": "Enabled", "KeyUsage": "ENCRYPT_DECRYPT", "KeySpec": "SYMMETRIC_DEFAULT"},
        ]}

    # --------------------------------------------------------------------- ecr
    def ecr(self) -> dict:
        repos = []
        for name in ["api-service", "worker", "frontend", "data-processor", "auth-service"]:
            repo_name = f"{self.env}/{name}"
            repos.append({
                "repositoryName": repo_name,
                "repositoryArn": arnf("ecr", self.region, f"repository/{repo_name}"),
                "repositoryUri": f"{ACCOUNT_ID}.dkr.ecr.{self.region}.amazonaws.com/{repo_name}",
                "imageTagMutability": "MUTABLE",
                "imageScanningConfiguration": {"scanOnPush": True},
                "images": [{"imageTag": "latest"}, {"imageTag": "v1.3.0"}, {"imageTag": "v1.2.9"}],
            })
        return {"repositories": repos}

    # ----------------------------------------------------------- elasticache
    def elasticache(self) -> dict:
        cluster_id = f"{self.env}-redis"
        rg_id      = f"{self.env}-redis-rg"
        return {
            "clusters": [{
                "CacheClusterId": cluster_id,
                "CacheClusterStatus": "available",
                "CacheNodeType": "cache.r6g.large",
                "Engine": "redis", "EngineVersion": "7.0.7",
                "NumCacheNodes": 1,
                "PreferredAvailabilityZone": self.az_a,
                "ReplicationGroupId": rg_id,
                "SecurityGroups": [{"SecurityGroupId": self.sg_cache, "Status": "active"}],
            }],
            "replication_groups": [{
                "ReplicationGroupId": rg_id,
                "Description": f"{self.env} Redis replication group",
                "Status": "available",
                "AutomaticFailover": "enabled", "MultiAZ": "enabled",
                "NodeGroups": [{"NodeGroupId": "0001", "Status": "available", "PrimaryEndpoint": {"Address": f"{rg_id}.abc123.ng.0001.{self.region}.cache.amazonaws.com", "Port": 6379}}],
                "AtRestEncryptionEnabled": True, "TransitEncryptionEnabled": True,
            }],
        }

    # ---------------------------------------------------------------- kinesis
    def kinesis(self) -> dict:
        sname = f"{self.env}-events"
        return {"streams": [{
            "StreamName": sname,
            "StreamARN": arnf("kinesis", self.region, f"stream/{sname}"),
            "StreamStatus": "ACTIVE",
            "Shards": [{"ShardId": f"shardId-{i:012d}"} for i in range(4)],
            "RetentionPeriodHours": 24,
            "EncryptionType": "KMS",
            "KeyId": self.kms_key_arn,
        }]}

    # --------------------------------------------------------- step_functions
    def step_functions(self) -> dict:
        name = f"{self.env}-order-workflow"
        return {"state_machines": [{
            "stateMachineArn": arnf("states", self.region, f"stateMachine:{name}"),
            "name": name, "type": "EXPRESS",
            "creationDate": "2025-03-01T00:00:00Z",
            "roleArn": arnf("iam", "", "role/lambda-exec-role"),
        }]}

    # ----------------------------------------------------------- api_gateway
    def api_gateway(self) -> dict:
        api_id    = _hex(10)
        v2_api_id = _hex(10)
        return {
            "rest_apis": [{
                "id": api_id, "name": f"{self.env}-rest-api",
                "description": f"{self.env} REST API",
                "createdDate": "2025-01-01T00:00:00Z",
                "stages": [
                    {"stageName": "v1", "deploymentId": _hex(8), "description": "Version 1"},
                ],
                "resources": [
                    {"id": _hex(10), "path": "/"},
                    {"id": _hex(10), "path": "/users",       "resourceMethods": {"GET": {}, "POST": {}}},
                    {"id": _hex(10), "path": "/users/{id}",  "resourceMethods": {"GET": {}, "PUT": {}, "DELETE": {}}},
                    {"id": _hex(10), "path": "/orders",      "resourceMethods": {"GET": {}, "POST": {}}},
                    {"id": _hex(10), "path": "/health",      "resourceMethods": {"GET": {}}},
                ],
            }],
            "http_websocket_apis": [{
                "ApiId": v2_api_id,
                "Name": f"{self.env}-http-api",
                "ProtocolType": "HTTP",
                "ApiEndpoint": f"https://{v2_api_id}.execute-api.{self.region}.amazonaws.com",
                "CreatedDate": "2025-06-01T00:00:00Z",
                "Tags": {"Environment": self.env},
                "stages": [{"StageName": "$default", "AutoDeploy": True}],
                "integrations": [
                    {"IntegrationId": _hex(8), "IntegrationType": "AWS_PROXY", "IntegrationUri": arnf("lambda", self.region, "function:api-handler")},
                    {"IntegrationId": _hex(8), "IntegrationType": "AWS_PROXY", "IntegrationUri": arnf("lambda", self.region, "function:auth-authorizer")},
                ],
                "routes": [
                    {"RouteId": _hex(8), "RouteKey": "GET /users"},
                    {"RouteId": _hex(8), "RouteKey": "POST /users"},
                    {"RouteId": _hex(8), "RouteKey": "GET /orders"},
                    {"RouteId": _hex(8), "RouteKey": "GET /health"},
                    {"RouteId": _hex(8), "RouteKey": "$default"},
                ],
            }],
        }

    # ---------------------------------------------------------------- redshift
    def redshift(self) -> dict:
        cluster_id = f"{self.env}-dwh"
        return {"clusters": [{
            "ClusterIdentifier": cluster_id,
            "NodeType": "ra3.xlplus", "ClusterStatus": "available",
            "MasterUsername": "admin", "DBName": "datawarehouse",
            "Endpoint": {"Address": f"{cluster_id}.{_hex(8)}.{self.region}.redshift.amazonaws.com", "Port": 5439},
            "NumberOfNodes": 2, "VpcId": self.vpc_main,
            "Encrypted": True, "KmsKeyId": self.kms_key_arn,
            "Tags": tags("Environment", self.env),
        }]}

    # ------------------------------------------------------------------- glue
    def glue(self) -> dict:
        return {
            "databases": [
                {"Name": f"{self.env}_analytics", "CreateTime": "2025-06-01T00:00:00Z", "LocationUri": "s3://acme-data-lake/analytics/"},
                {"Name": f"{self.env}_raw",        "CreateTime": "2025-06-01T00:00:00Z", "LocationUri": "s3://acme-data-lake/raw/"},
            ],
            "crawlers": [
                {"Name": f"{self.env}-s3-events-crawler", "State": "READY", "DatabaseName": f"{self.env}_raw",      "Targets": {"S3Targets": [{"Path": "s3://acme-data-lake/events/"}]}},
                {"Name": f"{self.env}-rds-crawler",        "State": "READY", "DatabaseName": f"{self.env}_analytics", "Targets": {"JdbcTargets": [{"ConnectionName": "prod-postgres"}]}},
            ],
            "jobs": [
                {"Name": f"{self.env}-etl-transform", "Role": arnf("iam", "", "role/glue-service-role"), "ExecutionProperty": {"MaxConcurrentRuns": 3}, "Command": {"Name": "glueetl", "ScriptLocation": "s3://acme-dev-artifacts/glue/etl-transform.py"}},
                {"Name": f"{self.env}-data-quality",  "Role": arnf("iam", "", "role/glue-service-role"), "ExecutionProperty": {"MaxConcurrentRuns": 1}, "Command": {"Name": "glueetl", "ScriptLocation": "s3://acme-dev-artifacts/glue/data-quality.py"}},
            ],
        }

    # --------------------------------------------------------------- cloudtrail
    def cloudtrail(self) -> dict:
        return {"trails": [{
            "Name": f"{self.env}-cloudtrail",
            "S3BucketName": "acme-prod-logs",
            "IsMultiRegionTrail": True, "HomeRegion": self.region,
            "HasCustomEventSelectors": True, "LogFileValidationEnabled": True,
            "TrailARN": arnf("cloudtrail", self.region, f"trail/{self.env}-cloudtrail"),
        }]}

    # ------------------------------------------------------------------ config
    def config(self) -> dict:
        return {
            "recorders": [{"name": "default", "roleARN": arnf("iam", "", "role/ec2-instance-role"), "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True}}],
            "rules": [
                {"ConfigRuleName": "encrypted-volumes",                   "ConfigRuleState": "ACTIVE", "Source": {"Owner": "AWS", "SourceIdentifier": "ENCRYPTED_VOLUMES"}},
                {"ConfigRuleName": "s3-bucket-public-read-prohibited",    "ConfigRuleState": "ACTIVE", "Source": {"Owner": "AWS", "SourceIdentifier": "S3_BUCKET_PUBLIC_READ_PROHIBITED"}},
                {"ConfigRuleName": "iam-root-access-key-check",           "ConfigRuleState": "ACTIVE", "Source": {"Owner": "AWS", "SourceIdentifier": "IAM_ROOT_ACCESS_KEY_CHECK"}},
                {"ConfigRuleName": "mfa-enabled-for-iam-console-access",  "ConfigRuleState": "ACTIVE", "Source": {"Owner": "AWS", "SourceIdentifier": "MFA_ENABLED_FOR_IAM_CONSOLE_ACCESS"}},
                {"ConfigRuleName": "rds-storage-encrypted",               "ConfigRuleState": "ACTIVE", "Source": {"Owner": "AWS", "SourceIdentifier": "RDS_STORAGE_ENCRYPTED"}},
            ],
        }

    # ------------------------------------------------------------------ wafv2
    def wafv2(self) -> dict:
        waf_id = _hex(36)
        return {"web_acls": [{
            "Name": "main-waf",
            "Id": waf_id,
            "ARN": arnf("wafv2", self.region, f"regional/webacl/main-waf/{waf_id}"),
            "Description": "Main WAF protecting ALB and API Gateway",
            "Capacity": 100,
        }]}

    # -------------------------------------------------------------------- acm
    def acm(self) -> dict:
        return {"certificates": [
            {"CertificateArn": arnf("acm", self.region, f"certificate/{_hex(36)}"), "DomainName": "acme-corp.com",          "Status": "ISSUED"},
            {"CertificateArn": arnf("acm", self.region, f"certificate/{_hex(36)}"), "DomainName": "*.acme-corp.com",        "Status": "ISSUED"},
            {"CertificateArn": arnf("acm", self.region, f"certificate/{_hex(36)}"), "DomainName": "internal.acme-corp.com", "Status": "ISSUED"},
        ]}

    # --------------------------------------------------------------- sagemaker
    def sagemaker(self) -> dict:
        return {
            "notebooks": [],
            "endpoints": [{
                "EndpointName": f"{self.env}-recommendation-model",
                "EndpointArn": arnf("sagemaker", self.region, f"endpoint/{self.env}-recommendation-model"),
                "EndpointStatus": "InService",
                "CreationTime": "2025-09-01T00:00:00Z",
            }],
            "models": [{
                "ModelName": f"{self.env}-recommendation-v2",
                "ModelArn": arnf("sagemaker", self.region, f"model/{self.env}-recommendation-v2"),
                "CreationTime": "2025-08-01T00:00:00Z",
            }],
        }

    # --------------------------------------------------------------------- emr
    def emr(self) -> dict:
        return {"clusters": []}

    # --------------------------------------------------------------- opensearch
    def opensearch(self) -> dict:
        domain_name = f"{self.env}-search"
        return {"domains": [{
            "DomainName": domain_name,
            "ARN": arnf("es", self.region, f"domain/{domain_name}"),
            "DomainId": f"{ACCOUNT_ID}/{domain_name}",
            "Endpoint": f"search-{domain_name}-{_hex(26)}.{self.region}.es.amazonaws.com",
            "EngineVersion": "OpenSearch_2.11",
            "ClusterConfig": {"InstanceType": "r6g.large.search", "InstanceCount": 3, "DedicatedMasterEnabled": True},
            "EncryptionAtRestOptions": {"Enabled": True, "KmsKeyId": self.kms_key_arn},
            "NodeToNodeEncryptionOptions": {"Enabled": True},
            "VPCOptions": {"VPCId": self.vpc_main, "SubnetIds": [self.sub_priv_a]},
        }]}

    # ------------------------------------------------------------------ backup
    def backup(self) -> dict:
        vault_name = f"{self.env}-backup-vault"
        plan_name  = f"{self.env}-backup-plan"
        return {
            "vaults": [{"BackupVaultName": vault_name, "BackupVaultArn": arnf("backup", self.region, f"backup-vault:{vault_name}"), "NumberOfRecoveryPoints": random.randint(50, 500), "EncryptionKeyArn": self.kms_key_arn}],
            "plans":  [{"BackupPlanId": _hex(36), "BackupPlanName": plan_name, "BackupPlanArn": arnf("backup", self.region, f"backup-plan:{_hex(36)}"), "VersionId": _hex(32)}],
        }

    # --------------------------------------------------------------- eventbridge
    def eventbridge(self) -> dict:
        return {
            "event_buses": [
                {"Name": "default",              "Arn": arnf("events", self.region, "event-bus/default")},
                {"Name": f"{self.env}-app-bus",  "Arn": arnf("events", self.region, f"event-bus/{self.env}-app-bus")},
            ],
            "rules": [
                {"Name": "nightly-cleanup",      "Arn": arnf("events", self.region, "rule/nightly-cleanup"),      "ScheduleExpression": "cron(0 2 * * ? *)", "State": "ENABLED"},
                {"Name": "hourly-report",         "Arn": arnf("events", self.region, "rule/hourly-report"),        "ScheduleExpression": "rate(1 hour)",       "State": "ENABLED"},
                {"Name": "deployment-completed",  "Arn": arnf("events", self.region, "rule/deployment-completed"), "EventPattern": '{"source":["aws.codepipeline"]}', "State": "ENABLED"},
                {"Name": "rds-maintenance",       "Arn": arnf("events", self.region, "rule/rds-maintenance"),      "ScheduleExpression": "cron(0 3 ? * SUN *)", "State": "ENABLED"},
            ],
        }

    # --------------------------------------------------------------------- efs
    def efs(self) -> dict:
        fs_id = f"fs-{_hex(8)}"
        return {"file_systems": [{
            "FileSystemId": fs_id,
            "FileSystemArn": arnf("elasticfilesystem", self.region, f"file-system/{fs_id}"),
            "Name": f"{self.env}-shared-storage",
            "LifeCycleState": "available",
            "NumberOfMountTargets": 2,
            "SizeInBytes": {"Value": random.randint(10**9, 10**12)},
            "PerformanceMode": "generalPurpose",
            "Encrypted": True, "KmsKeyId": self.kms_key_arn,
            "ThroughputMode": "bursting",
            "Tags": tags("Name", f"{self.env}-shared-storage", "Environment", self.env),
        }]}

    # ---------------------------------------------------------------- guardduty
    def guardduty(self) -> dict:
        return {"detector_ids": [_hex(32)]}

    # ----------------------------------------------------------------- cognito
    def cognito(self) -> dict:
        pool_id = f"{self.region}_{_hex(9)}"
        return {
            "user_pools": [{
                "Id": pool_id, "Name": f"{self.env}-users", "Status": "Enabled",
                "LastModifiedDate": "2025-12-01T00:00:00Z",
                "details": {
                    "Id": pool_id, "Name": f"{self.env}-users",
                    "Policies": {"PasswordPolicy": {"MinimumLength": 12, "RequireUppercase": True, "RequireLowercase": True, "RequireNumbers": True, "RequireSymbols": True}},
                    "MfaConfiguration": "OPTIONAL",
                    "EstimatedNumberOfUsers": random.randint(5000, 100_000),
                },
                "clients": [
                    {"ClientId": _hex(26), "ClientName": "web-app",    "UserPoolId": pool_id},
                    {"ClientId": _hex(26), "ClientName": "mobile-app", "UserPoolId": pool_id},
                ],
            }],
            "identity_pools": [{
                "IdentityPoolId": f"{self.region}:{str(uuid.UUID(int=random.getrandbits(128)))}",
                "IdentityPoolName": f"{self.env}-identity-pool",
                "AllowUnauthenticatedIdentities": False,
            }],
        }

    # --------------------------------------------------------------------- msk
    def msk(self) -> dict:
        cluster_name = f"{self.env}-kafka"
        return {"clusters": [{
            "ClusterName": cluster_name,
            "ClusterArn": arnf("kafka", self.region, f"cluster/{cluster_name}/{_hex(36)}"),
            "ClusterType": "PROVISIONED",
            "State": "ACTIVE",
            "CreationTime": "2025-04-01T00:00:00Z",
            "CurrentVersion": "K3P5RAKEXAMPLE",
            "Tags": {"Environment": self.env},
        }]}

    # --------------------------------------------------------------- firehose
    def firehose(self) -> dict:
        sname = f"{self.env}-log-delivery"
        return {"delivery_streams": [{
            "DeliveryStreamName": sname,
            "DeliveryStreamARN": arnf("firehose", self.region, f"deliverystream/{sname}"),
            "DeliveryStreamStatus": "ACTIVE",
            "DeliveryStreamType": "KinesisStreamAsSource",
            "Destinations": [{"S3DestinationDescription": {"BucketARN": arnf("s3", "", "acme-data-lake"), "BufferingHints": {"SizeInMBs": 128, "IntervalInSeconds": 300}}}],
        }]}

    # ------------------------------------------------------------------- batch
    def batch(self) -> dict:
        ce_name = f"{self.env}-compute-env"
        jq_name = f"{self.env}-job-queue"
        jd_name = f"{self.env}-etl-job"
        return {
            "compute_environments": [{
                "computeEnvironmentName": ce_name,
                "computeEnvironmentArn": arnf("batch", self.region, f"compute-environment/{ce_name}"),
                "state": "ENABLED", "status": "VALID", "type": "MANAGED",
                "computeResources": {"type": "SPOT", "instanceTypes": ["m5", "c5"], "maxvCpus": 256, "subnets": [self.sub_priv_a, self.sub_priv_b], "securityGroupIds": [self.sg_app]},
            }],
            "job_queues": [{
                "jobQueueName": jq_name,
                "jobQueueArn": arnf("batch", self.region, f"job-queue/{jq_name}"),
                "state": "ENABLED", "status": "VALID", "priority": 10,
                "computeEnvironmentOrder": [{"order": 1, "computeEnvironment": arnf("batch", self.region, f"compute-environment/{ce_name}")}],
            }],
            "job_definitions": [{
                "jobDefinitionName": jd_name,
                "jobDefinitionArn": arnf("batch", self.region, f"job-definition/{jd_name}:1"),
                "revision": 1, "status": "ACTIVE", "type": "container",
                "containerProperties": {"image": f"{ACCOUNT_ID}.dkr.ecr.{self.region}.amazonaws.com/{self.env}/data-processor:latest", "vcpus": 4, "memory": 8192},
            }],
        }

    # --------------------------------------------------------------- codecommit
    def codecommit(self) -> dict:
        return {"repositories": [
            {"repositoryId": str(uuid.UUID(int=random.getrandbits(128))), "repositoryName": "api",      "cloneUrlHttp": f"https://git-codecommit.{self.region}.amazonaws.com/v1/repos/api"},
            {"repositoryId": str(uuid.UUID(int=random.getrandbits(128))), "repositoryName": "frontend", "cloneUrlHttp": f"https://git-codecommit.{self.region}.amazonaws.com/v1/repos/frontend"},
            {"repositoryId": str(uuid.UUID(int=random.getrandbits(128))), "repositoryName": "infra",    "cloneUrlHttp": f"https://git-codecommit.{self.region}.amazonaws.com/v1/repos/infra"},
        ]}

    # --------------------------------------------------------------- codebuild
    def codebuild(self) -> dict:
        return {"projects": [
            {"name": "api-build",      "arn": arnf("codebuild", self.region, "project/api-build"),      "serviceRole": arnf("iam", "", "role/codepipeline-role"), "environment": {"type": "LINUX_CONTAINER", "image": "aws/codebuild/standard:7.0", "computeType": "BUILD_GENERAL1_SMALL"}, "source": {"type": "CODECOMMIT", "location": f"https://git-codecommit.{self.region}.amazonaws.com/v1/repos/api"}},
            {"name": "frontend-build", "arn": arnf("codebuild", self.region, "project/frontend-build"), "serviceRole": arnf("iam", "", "role/codepipeline-role"), "environment": {"type": "LINUX_CONTAINER", "image": "aws/codebuild/standard:7.0", "computeType": "BUILD_GENERAL1_MEDIUM"}, "source": {"type": "CODECOMMIT", "location": f"https://git-codecommit.{self.region}.amazonaws.com/v1/repos/frontend"}},
        ]}

    # ------------------------------------------------------------- codepipeline
    def codepipeline(self) -> dict:
        return {"pipelines": [
            {"name": "api-pipeline",      "roleArn": arnf("iam", "", "role/codepipeline-role"), "stages": [{"name": "Source"}, {"name": "Build"}, {"name": "Test"}, {"name": "Deploy-ECS"}]},
            {"name": "frontend-pipeline", "roleArn": arnf("iam", "", "role/codepipeline-role"), "stages": [{"name": "Source"}, {"name": "Build"}, {"name": "Deploy-S3"}]},
        ]}

    # ---------------------------------------------------------------- appsync
    def appsync(self) -> dict:
        api_id = _hex(26)
        return {"graphql_apis": [{
            "apiId": api_id,
            "name": f"{self.env}-graphql-api",
            "authenticationType": "AMAZON_COGNITO_USER_POOLS",
            "arn": arnf("appsync", self.region, f"apis/{api_id}"),
            "uris": {"GRAPHQL": f"https://{api_id}.appsync-api.{self.region}.amazonaws.com/graphql"},
            "tags": {"Environment": self.env},
        }]}

    # --------------------------------------------------------------- apprunner
    def apprunner(self) -> dict:
        svc_arn = arnf("apprunner", self.region, f"service/{self.env}-payments-api/{_hex(32)}")
        return {"services": [{
            "ServiceName": f"{self.env}-payments-api",
            "ServiceArn": svc_arn,
            "ServiceUrl": f"{_hex(12)}.{self.region}.awsapprunner.com",
            "Status": "RUNNING",
            "CreatedAt": "2025-10-01T00:00:00Z",
        }]}

    # ------------------------------------------------------------- securityhub
    def securityhub(self) -> dict:
        return {
            "hub": {"HubArn": arnf("securityhub", self.region, "hub/default"), "SubscribedAt": "2025-01-01T00:00:00Z", "AutoEnableControls": True},
            "standards": [
                {"StandardsSubscriptionArn": arnf("securityhub", self.region, "subscription/aws-foundational-security-best-practices/v/1.0.0"), "StandardsArn": "arn:aws:securityhub:us-east-1::standards/aws-foundational-security-best-practices/v/1.0.0", "StandardsStatus": "READY"},
                {"StandardsSubscriptionArn": arnf("securityhub", self.region, "subscription/cis-aws-foundations-benchmark/v/1.4.0"),             "StandardsArn": "arn:aws:securityhub:us-east-1::standards/cis-aws-foundations-benchmark/v/1.4.0",             "StandardsStatus": "READY"},
            ],
            "products": [],
        }

    # ---------------------------------------------------------------- lightsail
    def lightsail(self) -> dict:
        return {"instances": [], "load_balancers": [], "databases": [], "buckets": []}

    # --------------------------------------------------------------- inspector
    def inspector(self) -> dict:
        return {"coverage": [
            {"resourceId": {"ec2InstanceTags": {"Name": "app-server-1"}}, "resourceType": "AWS_EC2_INSTANCE",    "scanType": "PACKAGE",  "scanStatus": {"statusCode": "ACTIVE"}},
            {"resourceId": {"ec2InstanceTags": {"Name": "app-server-2"}}, "resourceType": "AWS_EC2_INSTANCE",    "scanType": "PACKAGE",  "scanStatus": {"statusCode": "ACTIVE"}},
            {"resourceId": {"lambdaFunctionName": "api-handler"},          "resourceType": "AWS_LAMBDA_FUNCTION", "scanType": "PACKAGE",  "scanStatus": {"statusCode": "ACTIVE"}},
            {"resourceId": {"lambdaFunctionName": "event-processor"},      "resourceType": "AWS_LAMBDA_FUNCTION", "scanType": "PACKAGE",  "scanStatus": {"statusCode": "ACTIVE"}},
        ]}

    # ------------------------------------------------------------------- macie
    def macie(self) -> dict:
        return {
            "status": {"Status": "ENABLED", "FindingPublishingFrequency": "FIFTEEN_MINUTES", "ServiceRole": arnf("iam", "", "role/AWSServiceRoleForAmazonMacie")},
            "findings": [],
        }

    # --------------------------------------------------------------- build all
    def build(self) -> dict:
        return {
            "ec2":             self.ec2(),
            "rds":             self.rds(),
            "lambda":          self.lambda_(),
            "ecs":             self.ecs(),
            "eks":             self.eks(),
            "elb":             self.elb(),
            "autoscaling":     self.autoscaling(),
            "dynamodb":        self.dynamodb(),
            "sqs":             self.sqs(),
            "sns":             self.sns(),
            "cloudwatch":      self.cloudwatch(),
            "cloudwatch_logs": self.cloudwatch_logs(),
            "cloudformation":  self.cloudformation(),
            "secrets_manager": self.secrets_manager(),
            "ssm":             self.ssm(),
            "kms":             self.kms(),
            "ecr":             self.ecr(),
            "elasticache":     self.elasticache(),
            "kinesis":         self.kinesis(),
            "step_functions":  self.step_functions(),
            "api_gateway":     self.api_gateway(),
            "redshift":        self.redshift(),
            "glue":            self.glue(),
            "cloudtrail":      self.cloudtrail(),
            "config":          self.config(),
            "wafv2":           self.wafv2(),
            "acm":             self.acm(),
            "sagemaker":       self.sagemaker(),
            "emr":             self.emr(),
            "opensearch":      self.opensearch(),
            "backup":          self.backup(),
            "eventbridge":     self.eventbridge(),
            "efs":             self.efs(),
            "guardduty":       self.guardduty(),
            "cognito":         self.cognito(),
            "msk":             self.msk(),
            "firehose":        self.firehose(),
            "batch":           self.batch(),
            "codecommit":      self.codecommit(),
            "codebuild":       self.codebuild(),
            "codepipeline":    self.codepipeline(),
            "appsync":         self.appsync(),
            "apprunner":       self.apprunner(),
            "securityhub":     self.securityhub(),
            "lightsail":       self.lightsail(),
            "inspector":       self.inspector(),
            "macie":           self.macie(),
        }


def build_secondary(region: str, cidr_prefix: str) -> dict:
    """Lighter secondary region — subset of services, fewer resources."""
    b = RegionBuilder(region, cidr_prefix, env="prod")
    d = b.build()

    # Keep only the most common services in the secondary region
    keep = {
        "ec2", "rds", "lambda", "elb", "autoscaling",
        "cloudwatch", "cloudwatch_logs", "cloudformation",
        "secrets_manager", "ssm", "kms", "acm",
        "cloudtrail", "config", "guardduty",
        "sqs", "sns", "dynamodb", "ecr",
    }
    d = {k: v for k, v in d.items() if k in keep}

    # Trim to a lighter footprint
    d["ec2"]["instances"]         = d["ec2"]["instances"][:2]
    d["lambda"]["functions"]      = d["lambda"]["functions"][:2]
    d["dynamodb"]["tables"]       = d["dynamodb"]["tables"][:2]
    d["rds"]["db_instances"]      = d["rds"]["db_instances"][:1]
    d["rds"]["db_clusters"]       = []
    d["rds"]["db_snapshots"]      = []
    d["cloudwatch"]["alarms"]     = d["cloudwatch"]["alarms"][:2]
    d["cloudwatch_logs"]["log_groups"] = d["cloudwatch_logs"]["log_groups"][:3]

    return d


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a fake AWS inventory JSON for testing.")
    parser.add_argument("--output", default="sample_inventory_generated.json", help="Output JSON path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (use different values for fresh data)")
    args = parser.parse_args()

    random.seed(args.seed)

    regions = ["us-east-1", "eu-west-1"]
    primary   = RegionBuilder("us-east-1", "10.0",   env="prod")
    primary_data   = primary.build()
    secondary_data = build_secondary("eu-west-1", "10.100")

    now = datetime.datetime.utcnow().isoformat() + "Z"

    inventory = {
        "metadata": {
            "ingestion_time": now,
            "regions_scanned": regions,
            "profile": "generated-sample",
            "summary": {
                "regions_with_resources": 2,
                "total_regional_service_region_pairs": len(primary_data) + len(secondary_data),
                "total_errors": 0,
                "global_services_collected": ["iam", "s3", "route53", "organizations", "cloudfront"],
            },
        },
        "global_services": {
            "iam":           build_iam(),
            "s3":            build_s3(),
            "route53":       build_route53(),
            "organizations": build_organizations(),
            "cloudfront":    build_cloudfront(),
        },
        "regional_services": {
            "us-east-1": primary_data,
            "eu-west-1": secondary_data,
        },
        "errors": {
            "global": [],
            "regional": {},
        },
    }

    with open(args.output, "w") as f:
        json.dump(inventory, f, indent=2, default=str)

    size_kb = len(json.dumps(inventory, default=str)) // 1024
    print(f"Generated: {args.output}")
    print(f"Size:      ~{size_kb} KB")
    print(f"Seed:      {args.seed}  (use --seed N for different data)")
    print(f"Regions:   {', '.join(regions)}")
    print(f"Services (us-east-1):  {len(primary_data)}")
    print(f"Services (eu-west-1):  {len(secondary_data)}")


if __name__ == "__main__":
    main()
