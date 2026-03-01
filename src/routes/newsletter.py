import os
import requests as req
from datetime import datetime
from functools import wraps

from flask import (Blueprint, jsonify, request, render_template,
                   redirect, session, current_app)
from flask_mail import Message

from src.models.user import db
from src.models.newsletter import Subscriber
from src.extensions import mail, limiter

newsletter_bp = Blueprint('newsletter', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect('/api/auth/login')
        return f(*args, **kwargs)
    return decorated


def _mail_configured():
    return bool(os.environ.get('SMTP_HOST', ''))


def _base_url():
    """Return portal base URL, works both inside and outside request context."""
    configured = os.environ.get('PORTAL_URL', '').rstrip('/')
    if configured:
        return configured
    try:
        return request.host_url.rstrip('/')
    except RuntimeError:
        return 'http://localhost:5000'


def _site_name():
    return os.environ.get('SITE_NAME', 'Plex Portal')


def _send_email(to, subject, template, **ctx):
    """Render *template* with ctx and send to *to*. Returns True on success."""
    if not _mail_configured():
        return False
    try:
        html = render_template(template, **ctx)
        msg = Message(subject=subject, recipients=[to], html=html)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email to {to} failed: {e}")
        return False


def _get_plex_content():
    """Pull recently-added items per library section from Plex REST API."""
    url   = os.environ.get('PLEX_SERVER_URL', '').rstrip('/')
    token = os.environ.get('PLEX_TOKEN', '')
    sections_data = {}

    if not url or not token:
        return sections_data

    headers = {'X-Plex-Token': token, 'Accept': 'application/json'}
    try:
        r = req.get(f"{url}/library/sections", headers=headers, timeout=8)
        if r.status_code != 200:
            return sections_data

        for section in r.json().get('MediaContainer', {}).get('Directory', []):
            stype  = section.get('type', '')
            stitle = section.get('title', 'Unknown')
            skey   = section.get('key')
            if stype not in ('movie', 'show') or not skey:
                continue

            ar = req.get(
                f"{url}/library/sections/{skey}/recentlyAdded",
                headers=headers,
                params={'X-Plex-Container-Size': 8},
                timeout=8,
            )
            if ar.status_code != 200:
                continue

            items = ar.json().get('MediaContainer', {}).get('Metadata', [])
            sections_data[stitle] = {
                'type': stype,
                'items': [
                    {
                        'title':   i.get('title', ''),
                        'year':    i.get('year', ''),
                        'summary': (i.get('summary') or '')[:180],
                        'rating':  i.get('audienceRating') or i.get('rating'),
                        'thumb':   (f"{url}{i['thumb']}?X-Plex-Token={token}"
                                    if i.get('thumb') else None),
                    }
                    for i in items[:6]
                ],
            }
    except Exception as e:
        current_app.logger.warning(f"Plex content fetch failed: {e}")

    return sections_data


def _get_recent_fulfilled():
    """Return recently-available requests from Overseerr."""
    ov_url = os.environ.get('OVERSEERR_URL', '').rstrip('/')
    ov_key = os.environ.get('OVERSEERR_API_KEY', '')
    fulfilled = []

    if not ov_url or not ov_key:
        return fulfilled

    try:
        r = req.get(
            f"{ov_url}/api/v1/request",
            headers={'X-Api-Key': ov_key},
            params={'take': 10, 'filter': 'available', 'sort': 'modified'},
            timeout=8,
        )
        if r.status_code == 200:
            for item in r.json().get('results', []):
                media = item.get('media', {})
                fulfilled.append({
                    'title': media.get('originalTitle', 'Unknown'),
                    'type':  item.get('type', 'movie'),
                    'poster': ('https://image.tmdb.org/t/p/w185' +
                               media['posterPath'] if media.get('posterPath') else None),
                })
    except Exception:
        pass

    return fulfilled


# ── Email dispatchers (also called by scheduler) ──────────────────────────────

def send_all_weekly_digests():
    """Compile Plex content and email all opted-in confirmed subscribers."""
    subscribers = Subscriber.query.filter_by(
        confirmed=True, notify_weekly=True
    ).all()
    if not subscribers:
        return 0

    plex_content   = _get_plex_content()
    ov_fulfilled   = _get_recent_fulfilled()
    site           = _site_name()
    base           = _base_url()
    digest_date    = datetime.utcnow().strftime('%B %d, %Y')
    sent_count     = 0

    for sub in subscribers:
        ok = _send_email(
            to=sub.email,
            subject=f"🎬 Weekly Update from {site}",
            template='email/weekly_digest.html',
            subscriber=sub,
            plex_content=plex_content,
            ov_fulfilled=ov_fulfilled,
            site_name=site,
            unsub_url=f"{base}/newsletter/unsubscribe/{sub.unsub_token}",
            digest_date=digest_date,
        )
        if ok:
            sub.last_emailed_at = datetime.utcnow()
            sent_count += 1

    try:
        db.session.commit()
    except Exception:
        pass

    return sent_count


# ── Routes ────────────────────────────────────────────────────────────────────

@newsletter_bp.route('/subscribe', methods=['GET', 'POST'])
@limiter.limit("6 per minute", methods=['POST'])
def subscribe():
    site = _site_name()
    if request.method == 'GET':
        return render_template('newsletter/subscribe.html', site_name=site)

    email          = (request.form.get('email') or '').strip().lower()
    name           = (request.form.get('name') or '').strip()
    plex_username  = (request.form.get('plex_username') or '').strip()
    notify_req     = bool(request.form.get('notify_requests'))
    notify_week    = bool(request.form.get('notify_weekly'))

    if not email or '@' not in email:
        return render_template('newsletter/subscribe.html',
                               error='Please enter a valid email address.',
                               site_name=site)

    existing = Subscriber.query.filter_by(email=email).first()
    if existing and existing.confirmed:
        return render_template('newsletter/subscribe.html',
                               error='This email is already subscribed.',
                               site_name=site)

    if existing:
        sub = existing
    else:
        sub = Subscriber.new(email=email, name=name or None,
                             plex_username=plex_username or None,
                             notify_requests=notify_req,
                             notify_weekly=notify_week)
        db.session.add(sub)
        db.session.commit()

    base = _base_url()
    sent = _send_email(
        to=email,
        subject=f"Confirm your subscription to {site}",
        template='email/confirmation.html',
        subscriber=sub,
        confirm_url=f"{base}/newsletter/confirm/{sub.confirm_token}",
        site_name=site,
    )

    return render_template('newsletter/subscribe_done.html',
                           email=email,
                           email_sent=sent,
                           mail_configured=_mail_configured(),
                           site_name=site)


@newsletter_bp.route('/confirm/<token>')
def confirm(token):
    sub = Subscriber.query.filter_by(confirm_token=token).first()
    if not sub:
        return render_template('newsletter/confirmed.html',
                               success=False,
                               message='This confirmation link is invalid or has expired.',
                               site_name=_site_name())

    sub.confirmed    = True
    sub.confirmed_at = datetime.utcnow()
    sub.confirm_token = None
    db.session.commit()

    return render_template('newsletter/confirmed.html',
                           success=True,
                           subscriber=sub,
                           site_name=_site_name())


@newsletter_bp.route('/unsubscribe/<token>')
def unsubscribe(token):
    sub = Subscriber.query.filter_by(unsub_token=token).first()
    if not sub:
        return render_template('newsletter/unsubscribed.html',
                               success=False,
                               message='This unsubscribe link is invalid.',
                               site_name=_site_name())

    email = sub.email
    db.session.delete(sub)
    db.session.commit()

    return render_template('newsletter/unsubscribed.html',
                           success=True,
                           email=email,
                           site_name=_site_name())


@newsletter_bp.route('/admin')
@_require_login
def admin():
    subscribers   = Subscriber.query.order_by(Subscriber.created_at.desc()).all()
    base          = _base_url()
    webhook_secret = os.environ.get('NEWSLETTER_WEBHOOK_SECRET', '')

    return render_template(
        'newsletter/admin.html',
        subscribers=subscribers,
        site_name=_site_name(),
        smtp_configured=_mail_configured(),
        smtp_host=os.environ.get('SMTP_HOST', ''),
        webhook_url=f"{base}/newsletter/webhook",
        webhook_secret=webhook_secret,
        subscribe_url=f"{base}/newsletter/subscribe",
        total=len(subscribers),
        confirmed=sum(1 for s in subscribers if s.confirmed),
    )


@newsletter_bp.route('/subscribers')
@_require_login
def list_subscribers():
    subs = Subscriber.query.order_by(Subscriber.created_at.desc()).all()
    return jsonify([{
        'id':             s.id,
        'email':          s.email,
        'name':           s.name or '',
        'plex_username':  s.plex_username or '',
        'confirmed':      s.confirmed,
        'notify_requests': s.notify_requests,
        'notify_weekly':  s.notify_weekly,
        'created_at':     s.created_at.isoformat() if s.created_at else None,
        'last_emailed_at': s.last_emailed_at.isoformat() if s.last_emailed_at else None,
    } for s in subs])


@newsletter_bp.route('/subscriber/<int:sub_id>', methods=['DELETE'])
@_require_login
def delete_subscriber(sub_id):
    sub = Subscriber.query.get_or_404(sub_id)
    db.session.delete(sub)
    db.session.commit()
    return jsonify({'success': True})


@newsletter_bp.route('/send-test', methods=['POST'])
@_require_login
@limiter.limit("5 per minute")
def send_test():
    data     = request.json or {}
    to_email = (data.get('email') or '').strip()
    if not to_email or '@' not in to_email:
        return jsonify({'success': False, 'message': 'Enter a valid email address'})
    if not _mail_configured():
        return jsonify({'success': False,
                        'message': 'SMTP not configured — add email settings via the Setup Wizard.'})

    ok = _send_email(to=to_email, subject=f"Test email from {_site_name()}",
                     template='email/test.html', site_name=_site_name())
    if ok:
        return jsonify({'success': True, 'message': f'Test email sent to {to_email}'})
    return jsonify({'success': False, 'message': 'Send failed — check SMTP settings and server logs.'})


@newsletter_bp.route('/send-weekly', methods=['POST'])
@_require_login
@limiter.limit("3 per hour")
def trigger_weekly():
    if not _mail_configured():
        return jsonify({'success': False, 'message': 'SMTP not configured'})
    try:
        count = send_all_weekly_digests()
        return jsonify({'success': True, 'message': f'Weekly digest sent to {count} subscriber(s)'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@newsletter_bp.route('/webhook', methods=['POST'])
@limiter.limit("60 per minute")
def overseerr_webhook():
    """Receive Overseerr webhook; notify the subscriber who requested the media."""
    # Optional HMAC / bearer-token validation
    expected = os.environ.get('NEWSLETTER_WEBHOOK_SECRET', '')
    if expected:
        auth_header = request.headers.get('Authorization', '')
        provided    = auth_header.replace('Bearer ', '').strip()
        if not provided:
            provided = (request.json or {}).get('webhook_secret', '')
        if provided != expected:
            return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}
    if data.get('notification_type') != 'MEDIA_AVAILABLE':
        return jsonify({'ok': True, 'skipped': True})

    media_title = data.get('subject', 'Your requested content')
    media_type  = data.get('media', {}).get('media_type', 'movie')
    poster_url  = data.get('image', '')
    req_info    = data.get('request', {})
    req_email   = (req_info.get('requestedBy_email') or '').lower()
    req_user    = req_info.get('requestedBy_username') or ''

    sub = None
    if req_email:
        sub = Subscriber.query.filter_by(
            email=req_email, confirmed=True, notify_requests=True
        ).first()
    if not sub and req_user:
        sub = Subscriber.query.filter_by(
            plex_username=req_user, confirmed=True, notify_requests=True
        ).first()

    if sub:
        base = _base_url()
        ok   = _send_email(
            to=sub.email,
            subject=f"🎬 {media_title} is now available on Plex!",
            template='email/request_available.html',
            subscriber=sub,
            media_title=media_title,
            media_type=media_type,
            poster_url=poster_url,
            plex_url=os.environ.get('PLEX_SERVER_URL', '#'),
            site_name=_site_name(),
            unsub_url=f"{base}/newsletter/unsubscribe/{sub.unsub_token}",
        )
        if ok:
            sub.last_emailed_at = datetime.utcnow()
            db.session.commit()

    return jsonify({'ok': True})


@newsletter_bp.route('/guide')
def guide():
    base = _base_url()
    return render_template(
        'newsletter/guide.html',
        site_name=_site_name(),
        smtp_configured=_mail_configured(),
        webhook_url=f"{base}/newsletter/webhook",
        subscribe_url=f"{base}/newsletter/subscribe",
        webhook_secret=os.environ.get('NEWSLETTER_WEBHOOK_SECRET', '(not set — add NEWSLETTER_WEBHOOK_SECRET to env)'),
    )
