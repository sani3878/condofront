import urllib.request
import urllib.error
import json
from flask import current_app


def _send(to_email, subject, body):
    """Core Resend API sender. Returns (success, error)."""
    api_key  = current_app.config.get('re_WdGydpV4_8WEfes16D3LVvB8K5aZyoQNQ', '')
    from_addr = current_app.config.get('MAIL_FROM', 'CondoFront <onboarding@resend.dev>')

    if not api_key:
        return False, 'RESEND_API_KEY not configured'

    payload = json.dumps({
        'from':    from_addr,
        'to':      [to_email],
        'subject': subject,
        'text':    body,
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        return False, f'HTTP {e.code}: {error_body}'
    except Exception as e:
        return False, str(e)


def send_verification_email(to_email, fullname, verify_url):
    subject = 'ยืนยันอีเมลของคุณ — CondoFront'
    body = f"""สวัสดีคุณ {fullname},

ขอบคุณที่สมัครใช้งาน CondoFront!

กรุณายืนยันอีเมลของคุณโดยคลิกลิงก์ด้านล่าง:

{verify_url}

ลิงก์นี้จะหมดอายุภายใน 24 ชั่วโมง

หากคุณไม่ได้สมัครสมาชิก กรุณาเพิกเฉยต่ออีเมลฉบับนี้

ทีมงาน CondoFront
"""
    return _send(to_email, subject, body)


def send_contact_email(name, email, mobile, message, customer_name=None, property_name=None):
    to_email = current_app.config.get('CONTACT_TO_EMAIL') or \
               current_app.config.get('SMTP_USER', '')

    if not to_email:
        return False, 'CONTACT_TO_EMAIL not configured'

    subject = f'[CondoFront] ข้อความใหม่จาก {name}'
    body = f"""มีข้อความใหม่จากผู้ใช้งาน CondoFront

ชื่อ: {name}
อีเมล: {email}
เบอร์โทร: {mobile or '-'}
บริษัท/ลูกค้า: {customer_name or '-'}
โครงการ: {property_name or '-'}

ข้อความ:
{message}
"""
    return _send(to_email, subject, body)
