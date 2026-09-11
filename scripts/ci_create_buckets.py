"""CI-only helper: creates the real avatars/documents/voice buckets
against the MinIO service container CI starts (S3-compatible, no real
cloud credentials needed). Moved out of .circleci/config.yml's own
`run:` step -- a literal `<<` heredoc there is a real, reserved
CircleCI 2.1 YAML token (merge key), which broke the pipeline with
"Unclosed '<<' tag" -- calling this real repo file instead avoids that
class of bug entirely rather than just escaping it, same real fix
recommended in CircleCI's own docs for exactly this situation."""

import boto3

client = boto3.client(
    "s3", endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin",
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
