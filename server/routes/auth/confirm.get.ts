import type { EmailOtpType } from '@supabase/supabase-js'
import { serverSupabaseClient } from '#supabase/server'

/**
 * Landing point for every Supabase auth email: signup confirmation, magic link,
 * password recovery and email-change.
 *
 * This runs on the server so the session cookie is set before the browser renders
 * anything. The user clicks the link in their inbox and arrives already signed in
 * — which is the whole point, because the previous flow dropped them on the home
 * page as an anonymous visitor and then asked them to fill their details in again.
 *
 * The route deliberately lives at /auth/confirm, not /confirm: /confirm is the
 * module's default `redirectOptions.callback`, where it expects a client-rendered
 * page, and /api/** is proxied to FastAPI by routeRules. /auth/** is neither.
 *
 * REQUIRED DASHBOARD CHANGE — Authentication > Emails > Confirm signup. The default
 * template uses `{{ .ConfirmationURL }}`, which only works in the browser that
 * started the signup (PKCE keeps the code verifier in a cookie there). Replace the
 * link with:
 *
 *   <a href="{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup">Confirm your email</a>
 *
 * That token is verified here instead, so confirming from a phone after signing up
 * on a laptop works. Do the same for the Magic Link, Change Email and Reset
 * Password templates, changing `type` to magiclink / email_change / recovery.
 *
 * Both flows are handled below regardless, so nothing breaks before that edit is made.
 */

const VALID_OTP_TYPES: readonly EmailOtpType[] = [
  'signup',
  'invite',
  'magiclink',
  'recovery',
  'email_change',
  'email',
]

/** Only ever redirect to a path on this site — never to an attacker-supplied host. */
function safeNext(value: unknown, fallback: string): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) {
    return fallback
  }
  return value
}

function loginWithError(message: string): string {
  return `/login?error=${encodeURIComponent(message)}`
}

export default defineEventHandler(async (event) => {
  const query = getQuery(event)

  // Supabase itself rejected the link (expired, already used, rate limited).
  const errorDescription = query.error_description ?? query.error
  if (typeof errorDescription === 'string' && errorDescription) {
    return sendRedirect(event, loginWithError(errorDescription), 302)
  }

  const type = query.type as EmailOtpType | undefined
  // A recovery link must land on the password form, not a generic account page.
  const next = safeNext(query.next, type === 'recovery' ? '/account?recovery=1' : '/account?welcome=1')

  const client = await serverSupabaseClient(event)

  // Preferred path: the email template passes a token hash we verify server-side.
  const tokenHash = query.token_hash
  if (typeof tokenHash === 'string' && tokenHash) {
    if (!type || !VALID_OTP_TYPES.includes(type)) {
      return sendRedirect(event, loginWithError('This confirmation link is malformed.'), 302)
    }

    const { error } = await client.auth.verifyOtp({ type, token_hash: tokenHash })
    if (error) {
      return sendRedirect(event, loginWithError(error.message), 302)
    }
    return sendRedirect(event, next, 302)
  }

  // Fallback: the stock `{{ .ConfirmationURL }}` template under the PKCE flow.
  const code = query.code
  if (typeof code === 'string' && code) {
    const { error } = await client.auth.exchangeCodeForSession(code)
    if (error) {
      return sendRedirect(event, loginWithError(error.message), 302)
    }
    return sendRedirect(event, next, 302)
  }

  // Fallback: the implicit flow puts the tokens in the URL fragment, which the
  // server never sees. Browsers carry a fragment across a redirect, so hand it to
  // a page where the Supabase browser client will pick it up itself.
  return sendRedirect(event, next, 302)
})
