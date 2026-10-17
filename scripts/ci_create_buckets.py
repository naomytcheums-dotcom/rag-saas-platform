"""CI-only helper: creates the real avatars/documents/voice buckets
against the MinIO service container CI starts (S3-compatible, no real
cloud credentials needed). Moved out of .circleci/config.yml's own
`run:` step -- a literal `<<` heredoc there is a real, reserved
CircleCI 2.1 YAML token (merge key), which broke the pipeline with
"Unclosed '<<' tag" -- calling this real repo file instead avoids that
class of bug entirely rather than just escaping it, same real fix
recommended in CircleCI's own docs for exactly this situation."""

import os

import boto3

# The endpoint and keys come from the environment so a local disposable MinIO on another port works; the defaults are CI's.
_endpoint = os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000")
if _endpoint.split("//", 1)[-1].split(":", 1)[0] not in ("localhost", "127.0.0.1"):
    raise SystemExit("refused: this helper only creates buckets on a local, throwaway S3 endpoint")
client = boto3.client(
    "s3", endpoint_url=_endpoint,
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID", "minioadmin"), aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY", "minioadmin"),
    region_name="us-east-1",
)
client.create_bucket(Bucket="avatars")
client.put_bucket_policy(Bucket="avatars", Policy="""{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::avatars/*"}]
}""")
# Partie 2.1.1 -- deliberately NO put_bucket_policy call here: documents must stay private, unlike avatars above.
client.create_bucket(Bucket="documents")
# Partie 8.2.7 -- same real reasoning: voice recordings stay private too.
client.create_bucket(Bucket="voice")
print("CI buckets created: avatars (public-read), documents (private), voice (private)")
