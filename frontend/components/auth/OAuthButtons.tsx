"use client";

import { fileUrl } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const PROVIDERS = ["google", "github"] as const;

/** "Continue with Google / GitHub" (spec 1.1.5 / 1.1.6). A plain link: the API redirects to the provider, then back to /oauth-callback
 * with the session in the URL fragment (api/routers/oauth.py). If the server has no credentials for a provider it answers 503, which the
 * browser shows as an error page: the buttons are therefore opt-in through NEXT_PUBLIC_OAUTH_PROVIDERS (comma separated, e.g. "google,github"). */
export default function OAuthButtons() {
  const { t } = useTranslation();
  const enabled = (process.env.NEXT_PUBLIC_OAUTH_PROVIDERS ?? "").split(",").map((p) => p.trim()).filter(Boolean);
  const providers = PROVIDERS.filter((p) => enabled.includes(p));
  if (providers.length === 0) return null;
  return (
    <div className="mt-6 flex flex-col gap-3" data-testid="oauth-buttons">
      <p className="text-center text-[13px] text-white/70">{t("auth.oauth.or")}</p>
      {providers.map((provider) => (
        <a
          key={provider}
          href={fileUrl(`/auth/oauth/${provider}/authorize`)}
          className="block h-[45px] rounded-full border-2 border-white/30 text-center text-base font-medium leading-[41px] text-white transition-colors hover:border-white/70"
        >
          {t(`auth.oauth.${provider}`)}
        </a>
      ))}
    </div>
  );
}
