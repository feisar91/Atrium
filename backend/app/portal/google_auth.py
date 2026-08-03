"""
Google OAuth guest sign-in.

Fixed, top-level routes (NOT nested under /p/<slug>) because Google requires
one exact, pre-registered redirect URI per OAuth client - a per-portal-slug
callback would need a separate registration in Google Cloud Console for every
portal an admin creates, which isn't workable. Instead there is exactly one
callback for the whole install, and the target portal plus the UniFi-supplied
context (mac/ap/ssid/redirect_url/t) travel through the signed `state` param.

On success, this hands off to the *existing* connect-token/success/finalize
pipeline in routes.py rather than talking to UnifiClient itself - Google is
just an alternate way to arrive at a valid connect-token.
"""

import logging
from urllib.parse import urlencode

import requests
from flask import Blueprint, current_app, redirect, render_template_string, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.models import GoogleAuthSettings, GuestAuthMethod, Portal
from .routes import _connect_serializer, _is_maintenance, _resolve_session_params

logger = logging.getLogger(__name__)

google_auth_bp = Blueprint("google_auth", __name__)

_STATE_SALT = "google-oauth-state"
_STATE_MAX_AGE = 600  # 10 minutes - generous enough for the guest to complete Google's consent screen

_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

_ERROR_PAGE = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Sign-in link expired</title>
<style>
  body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;
       min-height:100vh;margin:0;background:#f3f4f6}
  .box{background:#fff;border-radius:12px;padding:2rem 2.5rem;max-width:420px;
       text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.1)}
  h1{font-size:1.25rem;color:#111;margin-bottom:.5rem}
  p{color:#6b7280;font-size:.95rem}
</style>
</head>
<body><div class="box">
  <h1>Sign-in link expired</h1>
  <p>This Google sign-in link is no longer valid. Please reconnect to Wi-Fi and try again.</p>
</div></body>
</html>
"""


def _state_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_STATE_SALT)


def google_redirect_uri() -> str:
    """Absolute callback URL - must exactly match the URI registered in
    Google Cloud Console. Uses X-Forwarded-Proto rather than request.scheme:
    this app always sits behind the bundled nginx, which only ever speaks
    plain HTTP to gunicorn, so request.scheme reads "http" even when an
    SSL-terminating proxy sits in front of nginx. nginx forwards the real
    scheme in this header (see nginx/nginx.conf.template), sanitized against
    TRUSTED_PROXY_CIDR before it ever reaches Flask. Same convention used for
    the password reset/account setup links in app/api/auth.py."""
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    return f"{scheme}://{request.host}/auth/google/callback"


def _back_to_form(slug: str):
    """Send the guest back to their normal portal form - used for every
    failure path below (denied consent, expired code, Google API failure,
    config disabled mid-flow) so a broken/abandoned Google sign-in never
    dead-ends the guest, it just falls back to the regular form."""
    return redirect(url_for("portal.show_portal", slug=slug))


@google_auth_bp.route("/auth/google/start/<slug>")
def google_auth_start(slug):
    portal = Portal.query.filter_by(slug=slug, is_active=True).first_or_404()

    # Any of these failing means this link shouldn't have been shown at all
    # (stale bookmark, tampered link, or config changed after the guest page
    # was loaded) - degrade quietly back to the normal form rather than
    # erroring.
    if _is_maintenance(portal) or not portal.google_auth_enabled:
        return redirect(url_for("portal.show_portal", slug=slug, **request.args))

    settings = GoogleAuthSettings.get_or_create()
    if not (settings.enabled and settings.is_configured):
        return redirect(url_for("portal.show_portal", slug=slug, **request.args))

    state = _state_serializer().dumps({
        "portal_slug": slug,
        "mac": request.args.get("id", ""),
        "ap_mac": request.args.get("ap", ""),
        "ssid": request.args.get("ssid", ""),
        "redirect_url": portal.redirect_url or request.args.get("url", ""),
        "t": request.args.get("t", ""),
    })

    params = {
        "client_id": settings.client_id,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        # No refresh token needed - this is a one-shot identity check, not
        # an ongoing API integration.
        "access_type": "online",
        "prompt": "select_account",
    }
    return redirect(f"{_GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")


@google_auth_bp.route("/auth/google/callback")
def google_auth_callback():
    raw_state = request.args.get("state", "")
    try:
        payload = _state_serializer().loads(raw_state, max_age=_STATE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return render_template_string(_ERROR_PAGE), 400

    slug = payload.get("portal_slug", "")
    portal = Portal.query.filter_by(slug=slug, is_active=True).first()
    if not portal:
        return render_template_string(_ERROR_PAGE), 404

    # Google echoes `state` back even when the guest declined consent or hit
    # some other error, so we can still route them back to their own portal.
    if request.args.get("error"):
        return _back_to_form(slug)

    # Defense in depth: re-check everything that google_auth_start already
    # checked, since config could have changed during the round trip to Google.
    if _is_maintenance(portal) or not portal.google_auth_enabled:
        return _back_to_form(slug)

    settings = GoogleAuthSettings.get_or_create()
    if not (settings.enabled and settings.is_configured):
        return _back_to_form(slug)

    code = request.args.get("code", "")
    if not code:
        return _back_to_form(slug)

    try:
        token_resp = requests.post(_GOOGLE_TOKEN_ENDPOINT, data={
            "code": code,
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        }, timeout=10)
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise ValueError("no access_token in Google token response")

        userinfo_resp = requests.get(
            _GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.error("Google OAuth exchange failed for portal %s: %s", slug, e)
        return _back_to_form(slug)

    email = userinfo.get("email")
    # Google returns email_verified as a bool from this endpoint, but coerce
    # defensively since OAuth providers are inconsistent about bool vs "true".
    email_verified = str(userinfo.get("email_verified", "")).lower() == "true"
    if not email or not email_verified:
        return _back_to_form(slug)

    duration, rate_down, rate_up = _resolve_session_params(portal)

    token = _connect_serializer().dumps({
        "portal_id": portal.id,
        "mac": payload.get("mac", ""),
        "ap_mac": payload.get("ap_mac", ""),
        "ssid": payload.get("ssid", ""),
        "client_ip": request.headers.get("X-Real-IP") or request.remote_addr,
        "redirect_url": payload.get("redirect_url", ""),
        "duration": duration,
        "rate_down": rate_down,
        "rate_up": rate_up,
        "voucher_id": None,
        "form_data": {
            "auth_method": GuestAuthMethod.GOOGLE,
            "google_email": email,
            "google_name": userinfo.get("name", ""),
        },
        "auth_method": GuestAuthMethod.GOOGLE,
    })

    return redirect(url_for("portal.success", slug=portal.slug, token=token))
