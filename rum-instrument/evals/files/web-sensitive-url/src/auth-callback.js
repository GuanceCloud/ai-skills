// Synthetic authentication callback fixture; no actual credentials.
let accessToken;
export function readAuthenticationCallback() {
  accessToken = new URL(window.location.href).searchParams.get('access_token');
  return Boolean(accessToken);
}
