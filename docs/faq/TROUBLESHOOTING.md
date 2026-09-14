# FAQ — Troubleshooting

**Where's the detailed troubleshooting guide?**
[`docs/install/TROUBLESHOOTING.md`](../install/TROUBLESHOOTING.md)
covers install/deployment issues in depth. This page is quick pointers
for the most common questions.

**My documents never become "ready".** Check the ingestion pipeline is
running (`celery-worker` logs) — see
[Troubleshooting](../install/TROUBLESHOOTING.md) and
[Documents](../user/DOCUMENTS.md).

**Chat answers have no citations.** Confirm your documents finished
processing and that the query has actual relevant content to retrieve —
an assistant should say it can't find support rather than fabricate a
citation. See [Citations](../user/CITATIONS.md).

**Fine-tuning job fails immediately.** If targeting Anthropic, this is
expected — unsupported provider, see [Fine-tuning](../advanced/FINE_TUNING.md).
For OpenAI/Mistral, check the job's `failure_reason` for the real
provider error.

**Custom domain won't verify.** Almost always a DNS propagation or TXT
record issue — this step is manual, see [SSL & Domains](../install/SSL_AND_DOMAINS.md).

**API returns 429 constantly.** You're hitting rate limits, not quota —
see [Rate Limits](../api/RATE_LIMITS.md) and back off with
`Retry-After`.

**Still stuck?** See [`SECURITY.md`](../../SECURITY.md) for
vulnerabilities, or [`CONTRIBUTING.md`](../../CONTRIBUTING.md) for
filing a bug report.
