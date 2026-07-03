import requests
from twilio.rest import Client as TwilioClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import config

def _booking_url(lead_id: int) -> str:
    return f"{config.PUBLIC_BASE_URL}/book/{lead_id}"

def sms_template(name: str, lead_id: int) -> str:
    link = _booking_url(lead_id)
    return f"Hi {name}, thanks for reaching out! Are you available for a quick call? Book here: {link}"

def email_subject(name: str) -> str:
    return "Thanks for your inquiry!"

def email_body_template(name: str, lead_id: int) -> str:
    link = _booking_url(lead_id)
    return f"Hi {name},\n\nWe received your inquiry. Let's get you scheduled.\n\nBook here: {link}\n\nThanks,\nTeam"

def owner_new_lead_alert(name: str, source: str, lead_id: int) -> str:
    return f"A new lead ({name}) came in from {source}. They were auto-contacted."

def owner_reminder_alert(name: str, source: str, phone: str, minutes: int) -> str:
    return f"Reminder: Lead {name} from {source} ({phone}) hasn't booked after {minutes} minutes. Follow up!"

def send_sms(phone: str, message: str) -> dict:
    if not phone:
        return {"sent": False, "reason": "No phone provided"}

    if config.DEMO_MODE:
        return {"sent": True, "demo": True, "body": message}

    if not all([config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN, config.TWILIO_FROM_PHONE]):
        return {"sent": False, "error": "Missing Twilio credentials"}

    try:
        client = TwilioClient(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(body=message, from_=config.TWILIO_FROM_PHONE, to=phone)
        return {"sent": True, "body": message, "sid": msg.sid}
    except Exception as e:
        return {"sent": False, "error": str(e)}

def send_email(to_email: str, subject: str, body: str) -> dict:
    if not to_email:
        return {"sent": False, "reason": "No email provided"}

    if config.DEMO_MODE:
        return {"sent": True, "demo": True, "body": f"Subj: {subject}\n{body}"}

    if not all([config.SENDGRID_API_KEY, config.FROM_EMAIL]):
        return {"sent": False, "error": "Missing SendGrid credentials"}

    try:
        msg = Mail(from_email=config.FROM_EMAIL, to_emails=to_email, subject=subject, plain_text_content=body)
        sg = SendGridAPIClient(config.SENDGRID_API_KEY)
        sg.send(msg)
        return {"sent": True, "body": body}
    except Exception as e:
        return {"sent": False, "error": str(e)}

def send_slack_alert(message: str) -> dict:
    if not config.SLACK_WEBHOOK_URL:
        return {"sent": False, "reason": "No slack webhook URL"}

    if config.DEMO_MODE:
        return {"sent": True, "demo": True, "body": message}

    try:
        requests.post(config.SLACK_WEBHOOK_URL, json={"text": message})
        return {"sent": True, "body": message}
    except Exception as e:
        return {"sent": False, "error": str(e)}
