import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def _send(to_email, subject, body):
    """Core SMTP sender using SSL port 465. Returns (success, error)."""
    smtp_host = current_app.config.get('SMTP_HOST', '')
    smtp_port = int(current_app.config.get('SMTP_PORT', 465))
    smtp_user = current_app.config.get('SMTP_USER', '')
    smtp_pass = current_app.config.get('SMTP_PASS', '')
    from_addr = current_app.config.get('MAIL_FROM', smtp_user)

    if not smtp_user or not smtp_pass:
        return False, 'SMTP not configured'

    msg = MIMEMultipart()
    msg['From']     = from_addr
    msg['To']       = to_email
    msg['Subject']  = subject
    msg['Reply-To'] = smtp_user
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        return True, None
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
    to_email = current_app.config.get('CONTACT_TO_EMAIL', '')

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


def send_reset_email(to_email, fullname, reset_url):
    """Send a password reset email. Returns (success, error)."""
    subject = 'รีเซ็ตรหัสผ่าน — CondoFront'
    body = f"""สวัสดีคุณ {fullname},

เราได้รับคำขอรีเซ็ตรหัสผ่านสำหรับบัญชีของคุณ

คลิกลิงก์ด้านล่างเพื่อตั้งรหัสผ่านใหม่:

{reset_url}

ลิงก์นี้จะหมดอายุภายใน 1 ชั่วโมง

หากคุณไม่ได้ขอรีเซ็ตรหัสผ่าน กรุณาเพิกเฉยต่ออีเมลฉบับนี้
รหัสผ่านของคุณจะไม่ถูกเปลี่ยนแปลง

ทีมงาน CondoFront
"""
    return _send(to_email, subject, body)
