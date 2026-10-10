import TokenConfirmForm from "@/components/auth/TokenConfirmForm";

// MAP-003 -- linked from api/services/account_restore.py (`/restore-account?token=`); it used to be a 404.
export default function RestoreAccountPage() {
  return (
    <TokenConfirmForm
      title="Restore your account"
      subtitle="Your account is scheduled for deletion. Confirm to keep it."
      endpoint="/account/restore/confirm"
      button="Restore my account"
      busy="Restoring…"
      missingToken="This restore link is missing its token — request a new one."
    />
  );
}
