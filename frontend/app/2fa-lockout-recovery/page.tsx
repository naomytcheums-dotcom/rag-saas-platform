import TokenConfirmForm from "@/components/auth/TokenConfirmForm";

// MAP-003 -- linked from api/services/two_factor_lockout_recovery.py (`/2fa-lockout-recovery?token=`); it used to be a 404. The API
// refuses the confirmation (and says why) until the security delay after the request has passed.
export default function TwoFactorLockoutRecoveryPage() {
  return (
    <TokenConfirmForm
      title="Recover two-factor access"
      subtitle="Confirm to turn off two-factor authentication on your account."
      endpoint="/auth/2fa/lockout-recovery/confirm"
      button="Turn off two-factor"
      busy="Confirming…"
      missingToken="This recovery link is missing its token — request a new one."
    />
  );
}
