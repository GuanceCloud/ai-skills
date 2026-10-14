// Maintained authorization callback contract; synthetic fixture, no real credential.
let authSession = null;
export function handleAuthorizationCallback() {
  const token = new URL(window.location.href).searchParams.get('access_token');
  if (token) authSession = { accessToken: token };
  return Boolean(authSession);
}
// Intentionally retains the URL, matching the app behavior being assessed.
