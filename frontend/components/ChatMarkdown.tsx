"use client";

import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { Citation as CitationType } from "@/lib/types";
import Citation from "./Citation";
import CopyButton from "./CopyButton";

interface ChatMarkdownProps {
  text: string;
  citations?: CitationType[];
}

// Phase 5, Étape 9 -- real Markdown + syntax-highlighted code blocks for
// assistant messages, replacing MessageContent.tsx's own previous plain
// <p> rendering. `rehype-sanitize` runs on every render (real XSS
// defense against a malicious/compromised LLM response, not just
// against user input -- an assistant message is untrusted content the
// same way a document upload is).
//
// Real citation preservation, not a regression: `[n]` markers are
// rewritten to a real Markdown link `[n](citation:n)` BEFORE parsing,
// then the `a` renderer below intercepts the `citation:` scheme and
// swaps in the exact same real, clickable <Citation> component
// MessageContent.tsx already used -- a real link to an actual URL still
// renders as a real link, untouched.
function withCitationLinks(text: string): string {
  return text.replace(/\[(\d+)\]/g, (match, num) => `[${match}](citation:${num})`);
}

// Real, minimal extension of rehype-sanitize's own default schema
// (http/https/irc/ircs/mailto/xmpp only) -- without this, sanitization
// silently strips the `citation:` href scheme this component's own
// `withCitationLinks` relies on, degrading every citation back into
// plain "[n]" text. A REAL bug found by this component's own test
// suite (ChatMarkdown.test.tsx), not assumed.
const sanitizeSchema = {
  ...defaultSchema,
  protocols: { ...defaultSchema.protocols, href: [...(defaultSchema.protocols?.href ?? []), "citation"] },
};

// react-markdown's OWN built-in `defaultUrlTransform` runs independently
// of rehype-sanitize above and empties out any `href` scheme it doesn't
// itself recognize -- a second, real place this codebase's own tests
// caught the same `citation:` scheme being silently stripped, this time
// down to `href=""` rather than an outright-removed attribute.
function urlTransform(url: string): string {
  return url.startsWith("citation:") ? url : defaultUrlTransform(url);
}

export default function ChatMarkdown({ text, citations = [] }: ChatMarkdownProps) {
  const byNumber = new Map(citations.map((c) => [String(c.citation_number), c]));

  return (
    <div className="max-w-none text-sm leading-relaxed text-foreground [&_h1]:mt-3 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mt-2 [&_h3]:text-sm [&_h3]:font-semibold [&_li]:ml-4 [&_ol]:my-1.5 [&_ol]:list-decimal [&_p]:my-1.5 [&_strong]:font-semibold [&_table]:my-2 [&_table]:w-full [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-border [&_th]:bg-surface-muted [&_th]:px-2 [&_th]:py-1 [&_ul]:my-1.5 [&_ul]:list-disc">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
        urlTransform={urlTransform}
        components={{
          a({ href, children }) {
            if (href?.startsWith("citation:")) {
              const citation = byNumber.get(href.slice("citation:".length));
              return citation ? <Citation citation={citation} /> : <>{children}</>;
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const code = String(children).replace(/\n$/, "");
            if (!match) {
              return (
                <code className="rounded bg-surface-muted px-1 py-0.5 text-[0.85em]" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <div className="relative my-2">
                <div className="absolute right-2 top-2 z-10">
                  <CopyButton text={code} format="plain" />
                </div>
                <SyntaxHighlighter language={match[1]} style={vscDarkPlus} customStyle={{ margin: 0, borderRadius: "0.5rem" }}>
                  {code}
                </SyntaxHighlighter>
              </div>
            );
          },
        }}
      >
        {withCitationLinks(text)}
      </ReactMarkdown>
    </div>
  );
}
