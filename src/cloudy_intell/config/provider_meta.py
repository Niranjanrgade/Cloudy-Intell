"""Cloud provider metadata definitions.

Each provider carries its own domain-service mappings, prompt role labels,
validation checklists, and vector-store keys so that agent modules can render
provider-specific behaviour without hardcoding cloud vendor names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ProviderName = Literal["aws", "azure"]


@dataclass(frozen=True)
class ProviderMeta:
    """Immutable metadata for one cloud provider."""

    name: ProviderName
    display_name: str
    architect_role: str
    domain_services: dict[str, str]
    validation_checks: dict[str, str]
    rag_tool_description: str


# ── AWS ─────────────────────────────────────────────────────────────────────

AWS_META = ProviderMeta(
    name="aws",
    display_name="AWS",
    architect_role="AWS Principal Solutions Architect",
    domain_services={
        "compute": "EC2, Lambda, ECS, EKS, Auto Scaling, etc.",
        "network": "VPC, Subnets, ALB, CloudFront, Route 53, Security Groups, etc.",
        "storage": "S3, EBS, EFS, Glacier, etc.",
        "database": "RDS, DynamoDB, ElastiCache, etc.",
    },
    validation_checks={
        "compute": (
            "1. Service names and configurations are correct\n"
            "    2. Best practices are followed\n"
            "    3. Service compatibility and integration\n"
            "    4. Configuration parameters are valid\n"
            "    5. Any factual errors or misconfigurations"
        ),
        "network": (
            "1. VPC configuration (CIDR blocks, subnets, routing)\n"
            "    2. Security group rules and network ACLs\n"
            "    3. Load balancer configurations\n"
            "    4. DNS and CDN setup\n"
            "    5. Network connectivity and routing\n"
            "    6. Any factual errors or misconfigurations"
        ),
        "storage": (
            "1. S3 bucket configurations and policies\n"
            "    2. EBS volume types and configurations\n"
            "    3. EFS setup and performance modes\n"
            "    4. Storage lifecycle policies\n"
            "    5. Encryption and access controls\n"
            "    6. Any factual errors or misconfigurations"
        ),
        "database": (
            "1. Database engine selection and configuration\n"
            "    2. Instance types and sizing\n"
            "    3. Backup and recovery configurations\n"
            "    4. High availability and replication setup\n"
            "    5. Security and encryption settings\n"
            "    6. Any factual errors or misconfigurations"
        ),
    },
    rag_tool_description=(
        "Search AWS documentation vector database for accurate, up-to-date "
        "information about AWS services, configurations, and best practices."
    ),
)

# ── Azure ───────────────────────────────────────────────────────────────────

AZURE_META = ProviderMeta(
    name="azure",
    display_name="Azure",
    architect_role="Azure Principal Solutions Architect",
    domain_services={
        "compute": "Virtual Machines, Azure Functions, AKS, Container Apps, VM Scale Sets, etc.",
        "network": "VNet, Subnets, Application Gateway, Azure Front Door, Azure DNS, NSGs, etc.",
        "storage": "Blob Storage, Managed Disks, Azure Files, Archive Storage, etc.",
        "database": "Azure SQL, Cosmos DB, Azure Cache for Redis, Azure Database for PostgreSQL, etc.",
    },
    validation_checks={
        "compute": (
            "1. Service names and configurations are correct\n"
            "    2. Best practices are followed\n"
            "    3. Service compatibility and integration\n"
            "    4. Configuration parameters are valid\n"
            "    5. Any factual errors or misconfigurations"
        ),
        "network": (
            "1. VNet configuration (address spaces, subnets, routing)\n"
            "    2. NSG rules and network security\n"
            "    3. Load balancer and Application Gateway configurations\n"
            "    4. DNS and CDN setup (Azure DNS, Front Door)\n"
            "    5. Network connectivity and peering\n"
            "    6. Any factual errors or misconfigurations"
        ),
        "storage": (
            "1. Blob Storage container configurations and access policies\n"
            "    2. Managed Disk types and configurations\n"
            "    3. Azure Files setup and performance tiers\n"
            "    4. Storage lifecycle management policies\n"
            "    5. Encryption and access controls\n"
            "    6. Any factual errors or misconfigurations"
        ),
        "database": (
            "1. Database engine selection and configuration\n"
            "    2. Service tiers and sizing (DTU/vCore)\n"
            "    3. Backup and geo-replication configurations\n"
            "    4. High availability and failover setup\n"
            "    5. Security and encryption settings\n"
            "    6. Any factual errors or misconfigurations"
        ),
    },
    rag_tool_description=(
        "Search Azure documentation vector database for accurate, up-to-date "
        "information about Azure services, configurations, and best practices."
    ),
)

# ── Registry ────────────────────────────────────────────────────────────────

PROVIDER_REGISTRY: dict[ProviderName, ProviderMeta] = {
    "aws": AWS_META,
    "azure": AZURE_META,
}

DOMAINS = ("compute", "network", "storage", "database")


def get_provider_meta(name: ProviderName) -> ProviderMeta:
    """Retrieve provider metadata by canonical name."""
    return PROVIDER_REGISTRY[name]
