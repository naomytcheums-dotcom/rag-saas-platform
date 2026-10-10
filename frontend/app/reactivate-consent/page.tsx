import TokenConfirmForm from "@/components/auth/TokenConfirmForm";

// MAP-003 -- linked from api/services/consent_reactivation.py (`/reactivate-consent?token=`); it used to be a 404. The API requires
// accept_terms=true: consent is given again, not silently restored.
export default function ReactivateConsentPage() {
  return (
    <TokenConfirmForm
      title="Reactivate your account"
      subtitle="You withdrew your consent. Accept the terms again to use your account."
      endpoint="/account/consent/reactivate/confirm"
      button="Reactivate my account"
      busy="Reactivating…"
      missingToken="This reactivation link is missing its token — request a new one."
      termsLabel="I accept the terms of service"
    />
  );
}
