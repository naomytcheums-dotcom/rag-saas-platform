"use client";

import { DomainConfig } from "@/components/whitelabel/DomainConfig";
import { EmailConfig } from "@/components/whitelabel/EmailConfig";
import { FaviconUpload } from "@/components/whitelabel/FaviconUpload";
import { LogoUpload } from "@/components/whitelabel/LogoUpload";
import { PreviewBranding } from "@/components/whitelabel/PreviewBranding";
import { WhiteLabelConfig as WhiteLabelConfigForm } from "@/components/whitelabel/WhiteLabelConfig";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useWhiteLabel } from "@/lib/hooks/useWhiteLabel";

export function WhiteLabelPage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const orgId = org?.id ?? "";
  const {
    config, loading, error, update, uploadLogo, removeLogo, uploadFavicon,
    setDomain, removeDomain, verifyDomain, configureEmail, removeEmail, reset,
  } = useWhiteLabel(orgId);

  if (orgLoading || loading) {
    return <p className="text-sm text-foreground-muted">Loading…</p>;
  }

  if (error) {
    return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  }

  if (!config) return null;

  const handleReset = async () => {
    if (window.confirm("Reset your brand colors, name, custom CSS/JS and contact emails to platform defaults? Your logo, favicon, and custom domain are not affected.")) {
      await reset();
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">White-label</h1>
          <p className="mt-1 text-sm text-foreground-muted">Sell this platform under your own brand.</p>
        </div>
        <button type="button" onClick={() => void handleReset()} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground-muted hover:text-danger">
          Reset branding
        </button>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LogoUpload logoUrl={config.logo_url} onUpload={uploadLogo} onRemove={removeLogo} />
        <FaviconUpload faviconUrl={config.favicon_url} onUpload={uploadFavicon} />
      </div>

      <div className="mt-4">
        <WhiteLabelConfigForm config={config} onSave={update} />
      </div>

      <div className="mt-4">
        <DomainConfig domain={config.domain} domainVerified={config.domain_verified} onSet={setDomain} onRemove={removeDomain} onVerify={verifyDomain} />
      </div>

      <div className="mt-4">
        <EmailConfig senderName={config.email_sender_name} senderEmail={config.email_sender_email} onConfigure={configureEmail} onRemove={removeEmail} />
      </div>

      <h2 className="mt-6 text-sm font-medium text-foreground">Live preview</h2>
      <div className="mt-3">
        <PreviewBranding orgId={orgId} />
      </div>
    </div>
  );
}
