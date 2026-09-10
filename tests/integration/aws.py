"""Asking the emulator what is actually there.

**A green exit code is not evidence that anything was created.** These go and
look: after the application has applied, they ask S3, SQS and DynamoDB whether
the object exists; after it has destroyed, they ask whether it is gone.

`boto3` is already in the dependency ledger — it is what the credential and
exposure work reads — so this adds nothing.
"""

from __future__ import annotations

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Fail fast and do not retry. A verification that spends thirty seconds
# retrying against an emulator that has already answered is a test whose
# failure arrives long after the cause.
IMPATIENT = Config(
    retries={"max_attempts": 1, "mode": "standard"}, connect_timeout=5, read_timeout=15
)


DUMMY = "test"


def client(service: str, endpoint: str):
    return boto3.client(
        service,
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=DUMMY,
        # The emulator accepts any credentials, and these are the ones its own
        # documentation uses. Not a secret in any sense.
        aws_secret_access_key=DUMMY,  # noqa: S106
        config=IMPATIENT,
    )


def buckets(endpoint: str) -> set[str]:
    said = client("s3", endpoint).list_buckets()
    return {one["Name"] for one in said.get("Buckets", [])}


def queues(endpoint: str) -> set[str]:
    said = client("sqs", endpoint).list_queues()
    return {url.rsplit("/", 1)[-1] for url in said.get("QueueUrls", [])}


def queue_delay(endpoint: str, url: str) -> int:
    """What the queue actually says about itself, rather than what state says."""
    said = client("sqs", endpoint).get_queue_attributes(
        QueueUrl=url, AttributeNames=["DelaySeconds"]
    )
    return int(said["Attributes"]["DelaySeconds"])


def tables(endpoint: str) -> set[str]:
    return set(client("dynamodb", endpoint).list_tables().get("TableNames", []))


def set_queue_delay(endpoint: str, url: str, seconds: int) -> None:
    """Changes the queue **outside Terraform**, so a refresh has something real
    to find. This is the only thing here that writes."""
    client("sqs", endpoint).set_queue_attributes(
        QueueUrl=url, Attributes={"DelaySeconds": str(seconds)}
    )


def delete_bucket(endpoint: str, name: str) -> None:
    """Removes a bucket behind Terraform's back, for the case where a refresh
    has to notice something is gone."""
    s3 = client("s3", endpoint)
    try:
        s3.delete_bucket(Bucket=name)
    except ClientError:
        return
