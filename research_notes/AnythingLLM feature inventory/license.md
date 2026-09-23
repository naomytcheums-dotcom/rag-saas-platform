# AnythingLLM Licensing

## What is the exact license of the core AnythingLLM repository?

### Takeaway
The core `Mintplex-Labs/anything-llm` monorepo is licensed under the standard MIT License, copyright Mintplex Labs Inc., and this has been true since the repository's very first commit — it has never changed.

### Cited Findings
- The root `LICENSE` file at the repo root reads exactly: "The MIT License / Copyright (c) Mintplex Labs Inc." followed by the standard MIT permission/warranty text ("Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software...") — [LICENSE file](https://github.com/Mintplex-Labs/anything-llm/blob/master/LICENSE)
- GitHub's own repository metadata (license detection) reports: `"license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"}` — [GitHub API repo metadata](https://api.github.com/repos/Mintplex-Labs/anything-llm)
- The root README displays a license badge reading "license: MIT" linking to the LICENSE file, and its footer states: "Copyright © 2026 Mintplex Labs. This project is [MIT](./LICENSE) licensed." — [README.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/README.md)
- The root `package.json` declares `"license": "MIT"` — [package.json](https://github.com/Mintplex-Labs/anything-llm/blob/master/package.json)

### Inferences
- None needed; this is directly confirmed by primary source (LICENSE file text) plus corroborating GitHub metadata and README.

### Gaps
- None.

## Are all parts of the monorepo under the same license, or do specific subdirectories/packages carry a different license?

### Takeaway
Most of the monorepo (server, frontend, collector, docker configs) is MIT, matching the root license, and the `embed` widget and `browser-extension` directories are git submodules pointing to separate Mintplex Labs repositories that are also MIT-licensed. However, one subdirectory — `open-computer` — carries its own, separate **GNU Affero General Public License v3 (AGPLv3)** LICENSE file, distinct from the root MIT license.

### Cited Findings
- A full recursive tree listing of the repository (`git/trees/master?recursive=1`) shows exactly two `LICENSE` files in the whole repo: `LICENSE` (root) and `open-computer/LICENSE` — [GitHub Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1)
- `open-computer/LICENSE` is the full text of the GNU Affero General Public License, Version 3, 19 November 2007 ("Copyright (C) 2007 Free Software Foundation, Inc. ... The GNU Affero General Public License is a free, copyleft license for software and other kinds of works, specifically designed to ensure cooperation with the community in the case of network server software.") — [open-computer/LICENSE](https://github.com/Mintplex-Labs/anything-llm/blob/master/open-computer/LICENSE)
- `open-computer` is described in its own README as "Open Computer: Give your agent its own machine... a QEMU-based virtual desktop environment, purpose-built for AI agents," explicitly labeled "a work in progress" that the team "intend[s] to bring fully into AnythingLLM" — it is an experimental, separate sub-project bundled in the monorepo, not the core RAG/chat application — [open-computer/README.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/open-computer/README.md)
- `open-computer` itself bundles a QEMU submodule (`.gitmodules` → `[submodule "qemu"] url = https://gitlab.com/qemu-project/qemu.git`), and QEMU is separately licensed (predominantly GPLv2), which is consistent with why this subdirectory needed a copyleft (AGPLv3) license distinct from the rest of the MIT-licensed codebase — [open-computer/.gitmodules](https://github.com/Mintplex-Labs/anything-llm/blob/master/open-computer/.gitmodules)
- `server/package.json`, `frontend/package.json`, and `collector/package.json` each declare `"license": "MIT"` — [server/package.json](https://github.com/Mintplex-Labs/anything-llm/blob/master/server/package.json), [frontend/package.json](https://github.com/Mintplex-Labs/anything-llm/blob/master/frontend/package.json), [collector/package.json](https://github.com/Mintplex-Labs/anything-llm/blob/master/collector/package.json)
- `embed/` is a git submodule pointing to the separate repository `Mintplex-Labs/anythingllm-embed`; that repository's own `LICENSE` file is also the MIT License, copyright Mintplex Labs Inc., and GitHub's metadata for it confirms `"license": {"key": "mit", ...}` — [anythingllm-embed LICENSE](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/LICENSE), [anythingllm-embed repo metadata](https://api.github.com/repos/Mintplex-Labs/anythingllm-embed)
- `browser-extension/` is likewise a git submodule pointing to `Mintplex-Labs/anythingllm-extension`; that repo's `LICENSE` file is also the MIT License and GitHub metadata confirms `"license": {"key": "mit", ...}` — [anythingllm-extension LICENSE](https://github.com/Mintplex-Labs/anythingllm-extension/blob/master/LICENSE), [anythingllm-extension repo metadata](https://api.github.com/repos/Mintplex-Labs/anythingllm-extension)
- The `docker/` directory (Dockerfile, docker-compose.yml, entrypoint/healthcheck scripts, VEX vulnerability-exception JSON files) contains no separate LICENSE file of its own; it falls under the root MIT license by default as part of the monorepo — checked via the full recursive tree listing, confirmed no `docker/LICENSE` present — [GitHub Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1)
- No LICENSE file exists inside `/server`, `/frontend`, or `/collector` individually — checked directly against the full tree listing; only root `LICENSE` and `open-computer/LICENSE` appear — [GitHub Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1)
- The README lists related products explicitly: "**AnythingLLM Mobile (MIT Licensed)**: A mobile application..."; "**AnythingLLM Browser Extension**: A browser extension..."; "**AnythingLLM Embed**: A widget..." — [README.md "More Products" section](https://github.com/Mintplex-Labs/anything-llm/blob/master/README.md)

### Inferences
- The AGPLv3 license on `open-computer` is very likely inherited/required because that sub-project bundles QEMU (GPL-family licensed virtualization software) as a submodule; AGPL is a common choice when a project must remain copyleft-compatible with GPL dependencies while also closing the "network use" loophole that plain GPL leaves open. This is an inference from the presence of the QEMU submodule and the AGPL text's own stated purpose ("designed to ensure cooperation with the community in the case of network server software"), not a confirmed statement from Mintplex Labs.
- Because `open-computer` is explicitly described as "a work in progress" not yet part of the shipped AnythingLLM product, a company evaluating "AnythingLLM" for a commercial SaaS build would likely only be consuming the MIT-licensed core (server/frontend/collector) unless they specifically integrate the experimental open-computer subsystem — in which case AGPLv3 obligations (including source-disclosure for network-accessible modifications) would attach to that component specifically.

### Gaps
- No official Mintplex Labs blog post, docs page, or maintainer statement explicitly explains *why* `open-computer` uses AGPLv3 instead of MIT — this is inferred from the QEMU submodule dependency, not confirmed by a primary source.
- Could not directly confirm the `anythingllm-mobile` repo's LICENSE file text (only referenced via the README's "(MIT Licensed)" label); did not independently fetch that repo's raw LICENSE file to verify.

## Is there a dual-licensing model (open-core with a proprietary "Enterprise Edition" or paid closed-source add-ons)?

### Takeaway
There is no evidence of a dual-licensing model in the codebase itself — no proprietary "Enterprise Edition" source code, no BSL/commercial-license files, and no closed-source add-on packages were found anywhere in the monorepo or its submodules. Mintplex Labs monetizes via a separately-hosted managed cloud service and enterprise support/services (SSO, RBAC, white-glove on-prem installation), not via withholding source code or splitting the codebase into open/closed tiers.

### Cited Findings
- All code and package.json license fields found across the monorepo and its three linked submodules (embed, browser-extension, and by inference mobile) are MIT — no proprietary or "Enterprise License" text was found anywhere — [package.json license fields, multiple files above]
- AnythingLLM offers a paid "Cloud" hosted product starting reportedly around $50/month, aimed at "businesses or teams that need the power of AnythingLLM, but want a managed instance... so they don't have to sweat the technical details," and a "white-glove premium service package with on-premise support and installation" for enterprise needs — this is a hosting/support service model, not evidence of closed-source code — [WebSearch summary citing AnythingLLM Cloud page](https://anythingllm.com/cloud), [Elestio plans page](https://elest.io/open-source/anythingllm/resources/plans-and-pricing)
- The self-hosted Docker edition (the core product) is confirmed free and MIT-licensed — [WebSearch summary](https://useanything.com/pricing)
- A search of the recursive file tree for any BSL, SSPL, Elastic License, or "Enterprise" LICENSE files across the whole repository returned none — only `LICENSE` (root, MIT) and `open-computer/LICENSE` (AGPLv3) exist — [GitHub Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1)

### Inferences
- Mintplex Labs appears to run an "open source core + managed hosting/support" business model rather than a classic open-core (some features locked behind a proprietary license) model — every feature inspected so far (multi-user support, RBAC references, SSO) ships in the same MIT-licensed server code rather than a separate closed package. This is an inference based on absence of any separate proprietary repo/package; it was not exhaustively verified against every single feature flag in the server code.

### Gaps
- Did not exhaustively audit the `server/` codebase for feature flags that might gate SSO/RBAC behind a license key check (which could indicate an open-core pattern even without a separate proprietary repo). This would require deeper code review beyond license-file/metadata research and is out of scope for this pass.
- No official Mintplex Labs statement was found explicitly confirming "we do not have a closed-source Enterprise Edition" — the conclusion here is based on the absence of any such code/license artifacts, not a direct denial from the vendor.

## Does the MIT license permit forking, rebranding, removing branding, and reselling/redistributing commercially without restriction? Are there trademark restrictions on the "AnythingLLM" name/logo?

### Takeaway
The MIT License text itself is maximally permissive: it explicitly grants the right "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software," with the only condition being that the copyright notice and permission notice be retained in copies. This means forking, rebranding the code, and commercial resale/redistribution are permitted by the license text with no additional restriction beyond the notice-retention clause. However, MIT governs the *code*, not the *trademark* — no formal, published trademark policy or brand guidelines document from Mintplex Labs was found, and a real-world GitHub issue shows at least one user struggling to fully remove the AnythingLLM logo from the embeddable widget through supported customization options.

### Cited Findings
- The MIT License text explicitly states: "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." — [LICENSE](https://github.com/Mintplex-Labs/anything-llm/blob/master/LICENSE)
- No separate TRADEMARK, BRAND, or NOTICE file exists anywhere in the repository tree (confirmed via full recursive tree search for "notice", "trademark", "brand" — none found) — [GitHub Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1)
- A web search for a formal Mintplex Labs trademark policy or brand guidelines document for "AnythingLLM" returned no dedicated policy page — [WebSearch: Mintplex Labs trademark policy](no dedicated source found)
- GitHub issue #987, opened March 28, 2024 against the main repo, titled about widget rebranding, describes a user who followed the build instructions and replaced assets to rebrand the embedded chat widget but reports "I still see the anythingLLM logo," expressing concern the branding "does not look good on clients websites." The issue shows no visible maintainer response addressing licensing terms, official rebranding guidance, or permission requirements for full logo removal — [GitHub Issue #987](https://github.com/Mintplex-Labs/anything-llm/issues/987)

### Inferences
- Under MIT, a third party is legally free to fork the code, strip/replace all AnythingLLM branding in the source, and resell or redistribute a rebranded product commercially — the license places no restriction on commercial use, rebranding, or removing attribution *from the product's user-facing branding* (only the copyright/license notice must remain in the code/documentation, not in the running application's UI). This is a standard MIT interpretation, not something the repository states explicitly in a "commercial use FAQ."
- Even though the code is MIT, "AnythingLLM" as a product name/logo is a common-law (and potentially registered) trademark of Mintplex Labs Inc. by default under general trademark law — MIT licenses (like most OSS licenses) do not grant trademark rights, only copyright/code rights. Since no explicit trademark grant or disclaimer was found in the repo, a third party redistributing a fork should not use the "AnythingLLM" name or logo to describe their own commercial product/service in a way that implies affiliation or endorsement, even though the code itself can be freely reused. This is a general legal inference from standard OSS/trademark separation, not a specific policy statement from Mintplex Labs, because no such explicit policy document was found.
- The GitHub issue #987 evidence suggests that, in practice, the *supported* customization/build tooling for the embed widget did not (as of March 2024) make full logo removal straightforward for at least one user — this is anecdotal/practical evidence of friction in white-labeling, not a legal restriction, since the underlying code is still MIT and a determined forker could edit the source directly to remove the logo.

### Gaps
- Could not find any formal, dedicated Mintplex Labs trademark or brand-usage policy page (e.g., a TRADEMARK.md, a legal/brand-guidelines page on mintplexlabs.com or anythingllm.com) confirming explicit trademark restrictions or permissions — this is a real gap; the absence of a found policy does not prove no restrictions exist, since US/common-law trademark protection can apply by default without a published policy.
- Did not find a maintainer/company statement resolving GitHub issue #987 or otherwise explicitly confirming whether full whitelabel/logo removal is officially sanctioned for commercial resale of the embed widget.

## Attribution requirements — is there a NOTICE file, copyright headers, or other attribution obligations?

### Takeaway
The only attribution requirement found is the standard MIT License clause requiring the license/copyright notice to be included in copies of the software; no separate NOTICE file (as used by Apache-2.0 projects) exists anywhere in the repository.

### Cited Findings
- MIT License text: "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." — [LICENSE](https://github.com/Mintplex-Labs/anything-llm/blob/master/LICENSE)
- A search of the full recursive repository tree for any file with "NOTICE" in its path returned zero results — [GitHub Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1)

### Inferences
- Because MIT (unlike Apache-2.0) has no NOTICE-file mechanism and no per-file copyright-header mandate baked into the license text, the only strict legal attribution requirement for a redistributor is to keep the copyright/permission notice text (i.e., not delete the LICENSE file's content) somewhere in copies of the software — it does not require attribution to be visible in the running application's UI.

### Gaps
- Did not exhaustively check every individual source file in `/server`, `/frontend`, `/collector` for inline copyright header comments (e.g., `// Copyright (c) Mintplex Labs Inc.` at the top of files) — only the top-level LICENSE/NOTICE file question was verified via repository-tree search. If per-file headers exist, they would not add stricter requirements beyond the MIT terms already quoted above.

## Has the license changed at any point in the project's history (e.g., MIT/Apache to BSL/SSPL/Elastic License)?

### Takeaway
Confirmed: the AnythingLLM core license has NOT changed since the project's inception. The GitHub commit history for the `LICENSE` file shows only a single commit — the repository's "initial commit" on June 4, 2023 — meaning the MIT license has been in place, unmodified, for the entire public history of the project.

### Cited Findings
- Querying the GitHub Commits API filtered to the `LICENSE` file path (`/repos/Mintplex-Labs/anything-llm/commits?path=LICENSE`) returns exactly one commit, with the message "inital commit ⚡" dated 2023-06-04T02:28:07Z — indicating the LICENSE file was created at repo initialization and has never been edited since — [GitHub Commits API for LICENSE](https://api.github.com/repos/Mintplex-Labs/anything-llm/commits?path=LICENSE)
- This is corroborated by web search results describing AnythingLLM consistently as "MIT Licensed and Open Source" and "fully open-source" across multiple independent third-party sources discussing the current (2026) state of the project — [WebSearch summary](https://useanything.com/pricing), [WebSearch summary re: enterprise/cloud](https://anythingllm.com/cloud)

### Inferences
- Unlike some other AI/RAG open-source projects that relicensed from permissive to source-available licenses (e.g., Elastic License, BSL, SSPL) to prevent large cloud providers from reselling a hosted version, AnythingLXM's core repository shows no such history — it has remained MIT since June 2023, through the present (September 2026 as of this research).

### Gaps
- This analysis covers only the core `Mintplex-Labs/anything-llm` repository's `LICENSE` file history. It does not exhaustively confirm the license histories of the `anythingllm-embed`, `anythingllm-extension`, or `anythingllm-mobile` submodule repositories individually (each was spot-checked for its *current* license only, which is MIT in each case checked, but their commit histories for the LICENSE file were not queried).
- The `open-computer` subdirectory's AGPLv3 LICENSE file's own commit history was not checked to determine exactly when AGPLv3 was first added (i.e., whether open-computer started under a different license before AGPLv3, or was AGPLv3 from its first commit into the monorepo).

## Individual subdirectory LICENSE file check (/server, /frontend, /collector, /embed, /docker, /browser-extension)

### Takeaway
Directly confirmed via the GitHub API recursive tree listing (the authoritative way to enumerate every file in the repo): only two LICENSE files exist in the entire `Mintplex-Labs/anything-llm` repository — the root `LICENSE` (MIT) and `open-computer/LICENSE` (AGPLv3). None of `/server`, `/frontend`, `/collector`, or `/docker` contain their own LICENSE file; `/embed` and `/browser-extension` are git submodules whose linked repositories each carry their own MIT LICENSE file.

### Cited Findings
- `/server`: no LICENSE file present; `server/package.json` declares `"license": "MIT"`, inheriting the root license — [Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1), [server/package.json](https://github.com/Mintplex-Labs/anything-llm/blob/master/server/package.json)
- `/frontend`: no LICENSE file present; `frontend/package.json` declares `"license": "MIT"` — [Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1), [frontend/package.json](https://github.com/Mintplex-Labs/anything-llm/blob/master/frontend/package.json)
- `/collector`: no LICENSE file present; `collector/package.json` declares `"license": "MIT"` — [Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1), [collector/package.json](https://github.com/Mintplex-Labs/anything-llm/blob/master/collector/package.json)
- `/embed`: is a git submodule pointing to `Mintplex-Labs/anythingllm-embed`; that separate repo has its own root LICENSE file which is MIT — [anythingllm-embed LICENSE](https://github.com/Mintplex-Labs/anythingllm-embed/blob/main/LICENSE)
- `/docker`: no LICENSE file present (contains only Dockerfile, docker-compose.yml, entrypoint/healthcheck scripts, and VEX vulnerability-exception files); inherits the root MIT license — [Trees API](https://api.github.com/repos/Mintplex-Labs/anything-llm/git/trees/master?recursive=1)
- `/browser-extension`: is a git submodule pointing to `Mintplex-Labs/anythingllm-extension`; that separate repo has its own root LICENSE file which is MIT — [anythingllm-extension LICENSE](https://github.com/Mintplex-Labs/anythingllm-extension/blob/master/LICENSE)
- `/open-computer` (not in the original requested list, but discovered during research and material to the licensing picture): has its own LICENSE file, which is AGPLv3, distinct from the rest of the monorepo — [open-computer/LICENSE](https://github.com/Mintplex-Labs/anything-llm/blob/master/open-computer/LICENSE)

### Inferences
- None beyond what's stated above; this section is a direct factual enumeration.

### Gaps
- Did not check for a separate LICENSE file inside the `anythingllm-mobile` repository directly (only inferred MIT status from the README's parenthetical label "(MIT Licensed)"); recommend an independent check of `github.com/Mintplex-Labs/anythingllm-mobile/blob/main/LICENSE` if full verification of that specific product is required.
