import os
from dotenv import load_dotenv

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "secret_key_123")

# Public URL this app is reachable at once deployed (Render/Railway/your own
# domain). Used to build the /book/{id} links that go out over SMS/email.
# Left as localhost by default so local dev works with zero setup, but this
# MUST be set to your real deployed URL before going live - see README.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# Optional: set this to gate the dashboard + read APIs behind a single shared
# password (HTTP Basic Auth). Leave blank for open demo links. You SHOULD set
# this before sending a client's real lead data to a public URL.
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = os.getenv("TWILIO_FROM_PHONE")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

OWNER_EMAIL = os.getenv("OWNER_EMAIL")
OWNER_PHONE = os.getenv("OWNER_PHONE")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# 600s (10 min) matches the pitch: "pings the owner if it's not booked in
# 10 minutes." Drop this to 20-30s temporarily when running a LIVE client
# demo so the reminder fires while they're still watching the screen.
REMINDER_DELAY_SECONDS = int(os.getenv("REMINDER_DELAY_SECONDS", "600"))
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Your Local Business")
BOOKING_LINK = os.getenv("BOOKING_LINK", "https://calendly.com/your-link")
INDUSTRY_AVERAGE_RESPONSE_SECONDS = int(os.getenv("INDUSTRY_AVERAGE_RESPONSE_SECONDS", str(47 * 3600)))
