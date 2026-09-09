import Link from "next/link";

const FEATURES = [
  { icon: "💬", title: "RAG-powered chat", description: "Answers grounded in your own documents, with real citations.", href: "/chat" },
  { icon: "🤖", title: "Custom AI agents", description: "Configure prompts, tools, and guardrails per use case.", href: "/dashboard/agents" },
  { icon: "🧩", title: "Embeddable widget", description: "Drop a single script tag on any website.", href: "/dashboard/settings/widget" },
  { icon: "🔌", title: "Slack, Teams, Discord", description: "Bring your agents into the tools your team already uses.", href: "/dashboard/settings/integrations" },
  { icon: "🔑", title: "Public API", description: "Build on top of your own knowledge base with a real REST API.", href: "/dashboard/settings/api-keys" },
  { icon: "🔗", title: "Webhooks", description: "Real-time events delivered to your own systems.", href: "/dashboard/settings/webhooks" },
];

const STEPS = [
  { number: "1", title: "Upload your documents", description: "PDFs, docs, spreadsheets, websites — anything your team already has." },
  { number: "2", title: "Configure an agent", description: "Pick a prompt, guardrails, and the tools it's allowed to use." },
  { number: "3", title: "Deploy anywhere", description: "Your website, Slack, Teams, Discord, or your own app via the API." },
];

const FOOTER_COLUMNS = [
  { title: "Product", links: [{ label: "Chat demo", href: "/chat" }, { label: "Pricing", href: "/#pricing" }, { label: "Widget", href: "/dashboard/settings/widget" }] },
  { title: "Developers", links: [{ label: "API keys", href: "/dashboard/settings/api-keys" }, { label: "Webhooks", href: "/dashboard/settings/webhooks" }, { label: "API reference", href: "http://localhost:8000/docs" }] },
  { title: "Company", links: [{ label: "Log in", href: "/login" }, { label: "Sign up", href: "/register" }, { label: "Admin", href: "/admin" }] },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-orange-50 to-white">
      <header className="flex items-center justify-between px-6 py-4">
        <span className="text-lg font-semibold text-foreground">RAG SaaS Platform</span>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/login" className="text-foreground-muted transition-colors hover:text-foreground">Log in</Link>
          <Link href="/register" className="rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover">Get started</Link>
        </nav>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-20 text-center">
        <h1 className="text-4xl font-bold text-foreground sm:text-5xl">
          Build a RAG-powered assistant<br />for your business
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-foreground-muted">
          Upload your documents, configure an agent, and deploy a real chatbot — on your website, in Slack, or through your own app.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/register" className="rounded-lg bg-accent px-6 py-3 text-sm font-medium text-white transition-transform hover:-translate-y-0.5 hover:bg-accent-hover">Start for free</Link>
          <Link href="/chat" className="rounded-lg border border-border-strong px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-surface-muted">Try the demo</Link>
        </div>

        {/* Features */}
        <div className="mt-20 grid grid-cols-1 gap-5 text-left sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Link
              key={feature.title}
              href={feature.href}
              className="group rounded-xl border border-border bg-surface p-5 transition-all duration-200 hover:-translate-y-1 hover:border-accent hover:shadow-lg"
            >
              <span className="text-2xl" aria-hidden="true">{feature.icon}</span>
              <h3 className="mt-2 text-sm font-semibold text-foreground group-hover:text-accent-hover">{feature.title}</h3>
              <p className="mt-1 text-sm text-foreground-muted">{feature.description}</p>
              <span className="mt-2 inline-block text-xs font-medium text-accent opacity-0 transition-opacity group-hover:opacity-100">
                Explore →
              </span>
            </Link>
          ))}
        </div>

        {/* How it works */}
        <section className="mt-28">
          <h2 className="text-2xl font-semibold text-foreground">How it works</h2>
          <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
            {STEPS.map((step) => (
              <div key={step.number} className="rounded-xl border border-border bg-surface p-6 text-left transition-transform duration-200 hover:-translate-y-1">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-semibold text-white">{step.number}</span>
                <h3 className="mt-3 text-sm font-semibold text-foreground">{step.title}</h3>
                <p className="mt-1 text-sm text-foreground-muted">{step.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Stats */}
        <section className="mt-28 rounded-2xl border border-border bg-surface p-10">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <div>
              <p className="text-3xl font-bold text-accent">6</p>
              <p className="mt-1 text-sm text-foreground-muted">Languages supported</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-accent">3</p>
              <p className="mt-1 text-sm text-foreground-muted">Chat platform integrations</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-accent">3800+</p>
              <p className="mt-1 text-sm text-foreground-muted">Automated tests</p>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section id="pricing" className="mt-28 rounded-2xl bg-gradient-to-r from-accent to-orange-400 p-10 text-white">
          <h2 className="text-2xl font-semibold">Ready to build your assistant?</h2>
          <p className="mt-2 text-sm text-white/90">Create your organization in under a minute — no credit card required.</p>
          <Link href="/register" className="mt-5 inline-block rounded-lg bg-white px-6 py-3 text-sm font-medium text-accent-hover transition-transform hover:-translate-y-0.5">
            Start for free
          </Link>
        </section>
      </main>

      <footer className="border-t border-border bg-surface px-6 py-12">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <span className="text-sm font-semibold text-foreground">RAG SaaS Platform</span>
            <p className="mt-2 text-xs text-foreground-muted">Build and deploy AI assistants grounded in your own data.</p>
          </div>
          {FOOTER_COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">{column.title}</p>
              <div className="mt-2 flex flex-col gap-1.5">
                {column.links.map((link) => (
                  <Link key={link.label} href={link.href} className="text-sm text-foreground-muted transition-colors hover:text-accent">
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
        <p className="mx-auto mt-10 max-w-5xl text-xs text-foreground-muted">
          © {new Date().getFullYear()} RAG SaaS Platform. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
