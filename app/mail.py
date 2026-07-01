import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def send_verification_email(to_email, fullname, verify_url):
    """Send a welcome email with an email-verification link.

    Returns (success: bool, error_message: str|None)
    """
    smtp_host = current_app.config.get('SMTP_HOST')
    smtp_port = current_app.config.get('SMTP_PORT')
    smtp_user = current_app.config.get('SMTP_USER')
    smtp_pass = current_app.config.get('SMTP_PASS')

    if not smtp_user or not smtp_pass:
        return False, 'ระบบอีเมลยังไม่ได้ตั้งค่า (SMTP not configured)'

    subject = 'ยืนยันอีเมลของคุณ — CondoFront'

    body = f"""สวัสดีคุณ {fullname},

ขอบคุณที่สมัครใช้งาน CondoFront!

กรุณายืนยันอีเมลของคุณโดยคลิกลิงก์ด้านล่าง:

{verify_url}

ลิงก์นี้จะหมดอายุภายใน 24 ชั่วโมง

หากคุณไม่ได้สมัครสมาชิก กรุณาเพิกเฉยต่ออีเมลฉบับนี้

ทีมงาน CondoFront
"""

    msg = MIMEMultipart()
    msg['From']    = smtp_user
    msg['To']      = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def send_contact_email(name, email, mobile, message, customer_name=None, property_name=None):
    """Send a contact/feedback message to the support inbox via SMTP.

    Returns (success: bool, error_message: str|None)
    """
    smtp_host = current_app.config.get('SMTP_HOST')
    smtp_port = current_app.config.get('SMTP_PORT')
    smtp_user = current_app.config.get('SMTP_USER')
    smtp_pass = current_app.config.get('SMTP_PASS')
    to_email  = current_app.config.get('CONTACT_TO_EMAIL') or smtp_user

    if not smtp_user or not smtp_pass or not to_email:
        return False, 'ระบบอีเมลยังไม่ได้ตั้งค่า (SMTP not configured)'

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

    msg = MIMEMultipart()
    msg['From']    = smtp_user
    msg['To']      = to_email
    msg['Reply-To'] = email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)
