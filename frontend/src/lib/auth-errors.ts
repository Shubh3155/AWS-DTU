import { FirebaseError } from "firebase/app";

export function authMessage(error: unknown) {
  if (!(error instanceof FirebaseError)) return "Could not sign in. Please try again.";
  const messages: Record<string, string> = {
    "auth/popup-closed-by-user": "Sign-in cancelled. You can keep planning as a guest.",
    "auth/popup-blocked": "Your browser blocked the sign-in window. Allow popups for this site and try again.",
    "auth/unauthorized-domain": "Sign-in is not enabled for this website yet.",
    "auth/operation-not-allowed": "Google sign-in has not been enabled for this app yet.",
    "auth/network-request-failed": "Sign-in could not connect. Check your connection and try again.",
    "auth/account-exists-with-different-credential": "This account uses another sign-in method. Contact the app administrator.",
  };
  return messages[error.code] ?? "Could not sign in. Please try again.";
}
