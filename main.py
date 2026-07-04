import asyncio
import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import config
import database
import notifications
from demo_data import random_demo_lead
from models import LeadIn, StatusUpdate
from seed_db import seed as seed_demo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("speed_to_lead")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Speed-to-Lead Automation", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DashboardAuthMiddleware(BaseHTTPMiddleware):
    """Optional HTTP Basic Auth gate for the dashboard + read APIs.

    Only active if DASHBOARD_PASSWORD is set. Webhook/health endpoints are
    always exempt since they carry their own X-API-Key check (and Twilio/
    Zapier/Meta can't fill in a browser auth prompt anyway).
    """

    # Machine-to-machine endpoints keep their own X-API-Key check and must
    # stay reachable without a browser Basic Auth prompt: webhooks (Twilio/
    # Zapier/n8n), /simulate (dashboard demo button + open in demo mode),
    # /admin (API-key gated), and /book (the link a real lead clicks from
    # their SMS/email - they were never given the dashboard password).
    EXEMPT_PREFIXES = ("/webhook", "/health", "/simulate", "/admin", "/book")


    async def dispatch(self, request: Request, call_next):
        if not config.DASHBOARD_PASSWORD or request.url.path.startswith(self.EXEMPT_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
                _, _, password = decoded.partition(":")
                if password == config.DASHBOARD_PASSWORD:
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            status_code=401,
            content="Authentication required.",
            headers={"WWW-Authenticate": 'Basic realm="Speed-to-Lead Dashboard"'},
        )


app.add_middleware(DashboardAuthMiddleware)

database.init_db()

if config.DEMO_MODE:
    logger.info("Running in DEMO MODE - no real SMS/email will be sent. Set Twilio + SendGrid env vars to go live.")
else:
    logger.info("Running in LIVE MODE - real SMS/email will be sent.")
    if config.WEBHOOK_API_KEY == "secret_key_123":
        logger.warning("SECURITY: WEBHOOK_API_KEY is still the default value. Set a real secret in your env before going live.")
    if config.PUBLIC_BASE_URL.startswith("http://127.0.0.1"):
        logger.warning("PUBLIC_BASE_URL is still localhost - booking links sent by SMS/email will be broken for real leads. Set it to your deployed URL.")

if not config.DASHBOARD_PASSWORD:
    logger.info("DASHBOARD_PASSWORD is not set - the dashboard and lead data are open to anyone with the link. Set DASHBOARD_PASSWORD before sharing a client's real lead data.")

# Keep strong references to fire-and-forget reminder tasks so the event
# loop doesn't garbage-collect them mid-sleep (see Python asyncio docs).
_background_tasks: set = set()


def _track(task: "asyncio.Task") -> None:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = Query(default=None),
) -> bool:
    """Guards the paid-action endpoints. Accepts the key as a header
    (X-API-Key) or a query param (?key=...), since some webhook senders
    (e.g. Twilio status callbacks) can't set custom headers."""
    provided = x_api_key or key
    if provided != config.WEBHOOK_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


# ---- core pipeline --------------------------------------------------------------

def process_new_lead_sync(lead_id: int, name: str, email: Optional[str], phone: Optional[str], source: str, created_at: datetime) -> None:
    """Runs off the event loop (Starlette runs sync BackgroundTasks in a
    threadpool), so blocking network calls to Twilio/SendGrid are fine here."""
    sms_result = notifications.send_sms(phone, notifications.sms_template(name, lead_id))
    if sms_result.get("sent"):
        database.add_event(lead_id, "sms_sent_demo" if sms_result.get("demo") else "sms_sent", sms_result.get("body", ""))
    elif phone:
        database.add_event(lead_id, "sms_failed", sms_result.get("error") or sms_result.get("reason", ""))

    email_result = notifications.send_email(email, notifications.email_subject(name), notifications.email_body_template(name, lead_id))
    if email_result.get("sent"):
        database.add_event(lead_id, "email_sent_demo" if email_result.get("demo") else "email_sent", email_result.get("body", ""))
    elif email:
        database.add_event(lead_id, "email_failed", email_result.get("error") or email_result.get("reason", ""))

    if sms_result.get("sent") or email_result.get("sent"):
        elapsed_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
        database.mark_contacted(lead_id, elapsed_seconds)

    owner_msg = notifications.owner_new_lead_alert(name, source, lead_id)
    alerted = False
    if config.OWNER_EMAIL:
        notifications.send_email(config.OWNER_EMAIL, f"New lead: {name} via {source}", owner_msg)
        alerted = True
    if config.OWNER_PHONE:
        notifications.send_sms(config.OWNER_PHONE, owner_msg)
        alerted = True
    if config.SLACK_WEBHOOK_URL:
        notifications.send_slack_alert(f":rotating_light: {owner_msg}")
        alerted = True

    database.add_event(
        lead_id,
        "owner_alerted",
        owner_msg if alerted else "No owner contact configured (set OWNER_EMAIL / OWNER_PHONE / SLACK_WEBHOOK_URL)",
    )


async def schedule_reminder(lead_id: int, name: str, source: str, phone: Optional[str]) -> None:
    """Waits REMINDER_DELAY_SECONDS, then nudges the owner if the lead
    still hasn't booked. Cheap no-op if they already booked or were marked
    Lost - see database.needs_reminder."""
    try:
        await asyncio.sleep(config.REMINDER_DELAY_SECONDS)
        if not database.needs_reminder(lead_id):
            return

        minutes = max(1, round(config.REMINDER_DELAY_SECONDS / 60))
        msg = notifications.owner_reminder_alert(name, source, phone, minutes)
        if config.OWNER_EMAIL:
            await asyncio.to_thread(notifications.send_email, config.OWNER_EMAIL, f"Follow up: {name} hasn't booked", msg)
        if config.OWNER_PHONE:
            await asyncio.to_thread(notifications.send_sms, config.OWNER_PHONE, msg)
        if config.SLACK_WEBHOOK_URL:
            await asyncio.to_thread(notifications.send_slack_alert, f":alarm_clock: {msg}")

        database.mark_reminder_sent(lead_id)
        database.add_event(lead_id, "reminder_sent", msg)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 - a failed reminder must never crash the app
        logger.error("Reminder task failed for lead %s: %s", lead_id, e)


def _kick_off_pipeline(background_tasks: BackgroundTasks, name: str, email: Optional[str], phone: Optional[str], source: str, message: Optional[str]) -> int:
    created_at = datetime.now(timezone.utc)
    lead_id = database.create_lead(name=name, email=email, phone=phone, source=source, message=message, created_at=created_at)
    background_tasks.add_task(process_new_lead_sync, lead_id, name, email, phone, source, created_at)
    _track(asyncio.create_task(schedule_reminder(lead_id, name, source, phone)))
    return lead_id


# ---- routes -----------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "demo_mode": config.DEMO_MODE, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/config")
async def get_public_config():
    """Non-secret settings the dashboard needs to render itself correctly."""
    return {
        "demo_mode": config.DEMO_MODE,
        "business_name": config.BUSINESS_NAME,
        "booking_link": config.BOOKING_LINK,
        "reminder_delay_seconds": config.REMINDER_DELAY_SECONDS,
        "industry_avg_seconds": config.INDUSTRY_AVERAGE_RESPONSE_SECONDS,
    }


@app.post("/webhook/new-lead", status_code=201)
async def receive_lead(lead: LeadIn, background_tasks: BackgroundTasks, _auth: bool = Depends(verify_api_key)):
    """Point Zapier / Make / n8n / a website form / Meta Lead Ads here."""
    lead_id = _kick_off_pipeline(background_tasks, lead.name, lead.email, lead.phone, lead.source, lead.message)
    return {"status": "success", "lead_id": lead_id, "message": "Lead received - instant outreach in progress."}


@app.post("/webhook/missed-call")
async def receive_missed_call(request: Request, background_tasks: BackgroundTasks, _auth: bool = Depends(verify_api_key)):
    """Point a Twilio number's Voice status callback here to turn a missed
    call into a lead automatically. Expects Twilio's standard form-encoded
    callback body (From, CallStatus, ...)."""
    form = await request.form()
    call_status = str(form.get("CallStatus", "")).lower()
    from_number = str(form.get("From", "")) or None

    if call_status not in ("no-answer", "busy", "failed"):
        return {"status": "ignored", "reason": f"call status '{call_status}' doesn't need follow-up"}
    if not from_number:
        return {"status": "ignored", "reason": "no caller number provided"}

    lead_id = _kick_off_pipeline(background_tasks, "Missed Call Lead", None, from_number, "Missed Call", None)
    return {"status": "success", "lead_id": lead_id}


@app.post("/simulate/new-lead")
async def simulate_lead(background_tasks: BackgroundTasks, x_api_key: Optional[str] = Header(default=None)):
    """Powers the dashboard's 'Simulate New Lead' button. Free and
    unauthenticated in demo mode; requires the API key once real
    credentials are configured, so a public demo link can't run up a
    Twilio/SendGrid bill."""
    if not config.DEMO_MODE and x_api_key != config.WEBHOOK_API_KEY:
        raise HTTPException(status_code=401, detail="Live mode is active - provide X-API-Key to simulate a real send.")

    demo = random_demo_lead()
    lead_id = _kick_off_pipeline(background_tasks, demo["name"], demo["email"], demo["phone"], demo["source"], demo["message"])
    return {"status": "success", "lead_id": lead_id, "lead": demo}


@app.post("/admin/reset")
async def reset_demo_data(_auth: bool = Depends(verify_api_key)):
    """Wipes all leads/events. Handy for clearing fake demo leads right
    before a live client call, or clearing a client's data between trials."""
    database.reset_all()
    return {"status": "success", "message": "All leads and events cleared."}


@app.post("/admin/seed")
async def seed_demo_data(count: int = Query(default=8, ge=1, le=50), _auth: bool = Depends(verify_api_key)):
    """Populates the dashboard with realistic-looking fake leads spread over
    the past 24 hours - so a client clicking an async link (no live call)
    sees a 'lived-in' dashboard instead of an empty one. Exists because free
    hosting tiers (Render free, etc.) wipe local files on every spin-down,
    so there's no shell access to run a seed script directly - hit this
    endpoint instead, any time, from anywhere: no CLI needed.
    Runs on top of whatever's already there - call /admin/reset first if you
    want a completely clean slate."""
    created = seed_demo(count)
    return {"status": "success", "leads_created": created}


@app.get("/leads")
async def get_leads(status: Optional[str] = Query(default=None), limit: int = Query(default=200, le=500)):
    return {"leads": database.list_leads(status_filter=status, limit=limit)}


@app.get("/leads/{lead_id}")
async def get_lead_detail(lead_id: int):
    lead = database.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead["events"] = database.list_events(lead_id=lead_id, limit=50)
    return lead


@app.patch("/leads/{lead_id}/status")
async def patch_lead_status(lead_id: int, payload: StatusUpdate):
    lead = database.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    database.update_status(lead_id, payload.status)
    database.add_event(lead_id, "status_changed", f"Status manually set to {payload.status}")
    return {"status": "success", "lead_id": lead_id, "new_status": payload.status}


@app.get("/book/{lead_id}")
async def book_lead(lead_id: int):
    """The link every SMS/email actually contains. Marks the lead Booked
    (an MVP proxy for 'clicked through to schedule'), then forwards them
    to the real booking page. Falls back gracefully for unknown ids."""
    lead = database.get_lead(lead_id)
    if lead and lead["status"] != "Booked":
        database.update_status(lead_id, "Booked")
        database.add_event(lead_id, "link_clicked", "Lead clicked their booking link and was marked Booked")
    return RedirectResponse(url=config.BOOKING_LINK, status_code=307)


@app.get("/events")
async def get_events(limit: int = Query(default=30, le=200)):
    return {"events": database.list_events(limit=limit)}


@app.get("/stats")
async def get_stats():
    return database.get_stats()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Serve the dashboard (and any static assets) for everything not matched
# above. Must be mounted last so it doesn't shadow the API routes.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
