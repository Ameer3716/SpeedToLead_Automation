# Speed-to-Lead Automation

Auto-texts and auto-emails every new lead within seconds of them coming in,
logs everything to a live dashboard, and pings the business owner if the
lead still hasn't booked after 10 minutes.

The pitch: businesses that respond to a lead within 5 minutes are ~100x more
likely to make contact than one that waits 30 — and the average business
takes 47 hours. This closes that gap automatically.

---

## 1. What's actually in this project

A small FastAPI backend + one static HTML dashboard. No database server to
install (SQLite file), no separate frontend build step.

```
SpeedToLead_Automation/
├── main.py            # FastAPI app: routes, webhook auth, the pipeline
├── config.py           # all settings, read from environment variables
├── database.py         # SQLite reads/writes (leads + events tables)
├── notifications.py     # Twilio SMS / SendGrid email / Slack senders
├── demo_data.py         # fake leads for the "Simulate new lead" button
├── models.py            # request/response schemas
├── static/index.html    # the live dashboard (single file, no build step)
├── requirements.txt
├── .env.example          # copy to .env and fill in
├── Dockerfile             # deploy anywhere that runs a container
└── Procfile               # deploy on Render/Railway without Docker
```

### How a lead flows through it

1. A lead comes in — a webhook hits `POST /webhook/new-lead` (or Twilio hits
   `/webhook/missed-call` when a call goes unanswered).
2. The lead is saved to SQLite immediately.
3. In the background (doesn't block the response): an SMS goes out via
   Twilio, an email goes out via SendGrid, both containing a `/book/{id}`
   link. The owner gets alerted via email/SMS/Slack (whichever is
   configured).
4. A timer starts. If the lead hasn't clicked their booking link in
   `REMINDER_DELAY_SECONDS` (10 min by default), the owner gets a nagging
   follow-up alert automatically.
5. When the lead clicks their link, `/book/{id}` marks them **Booked** and
   forwards them to the real booking page (Calendly, etc.).
6. The dashboard polls `/leads`, `/events`, `/stats` every 4 seconds and
   shows all of this live — response time ticking up in real time, a feed
   of every SMS/email/alert as it fires, and a conversion rate.

**Demo Mode** (`DEMO_MODE=true`, the default) does all of the above except
it logs what the SMS/email *would* say instead of actually sending it — so
you can show the whole flow to a client with zero Twilio/SendGrid setup and
zero cost. Flip one variable to go live later.

---

## 2. Run it locally (2 minutes)

```bash
cd SpeedToLead_Automation
pip install -r requirements.txt
cp .env.example .env          # defaults are demo-safe, edit BUSINESS_NAME at least
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** — that's the dashboard. Click **Simulate new
lead** and watch it respond in real time.

---

## 3. Deploy it so you have a live link to show a client

You want a real URL (not localhost) before pitching anyone. **Render.com**
free tier is the fastest path and needs no credit card:

1. Push this folder to a GitHub repo.
2. Render.com → New → Web Service → connect the repo.
3. Render auto-detects the `Procfile`. If it asks: Build command
   `pip install -r requirements.txt`, Start command
   `uvicorn main:app --host 0.0.0.0 --port $PORT`.
4. Add environment variables (Render dashboard → Environment): at minimum
   set `BUSINESS_NAME` and `PUBLIC_BASE_URL` to the `https://your-app.onrender.com`
   URL Render gives you **after** the first deploy (redeploy once you know it).
5. Deploy. You now have a shareable link.

Prefer Docker (Railway, Fly.io, your own VPS)? The included `Dockerfile`
works as-is — `docker build -t speedtolead . && docker run -p 8000:8000 --env-file .env speedtolead`.

**Before sending the link to anyone:** set `DASHBOARD_PASSWORD` in your
environment variables. Without it, anyone with the URL can see every lead's
name, phone, and email — fine while it's just fake demo data, not fine once
it's a real client's real leads. Once set, the dashboard prompts for a
username (anything) + that password.

---

## 4. Wiring up real lead sources (for an actual client, not the demo)

Every source below just needs to `POST` to your deployed
`/webhook/new-lead` with header `X-API-Key: <your WEBHOOK_API_KEY>` and a
JSON body like `{"name": "...", "email": "...", "phone": "...", "source": "..."}`.

- **Website contact form** → point the form's submit handler (or a hidden
  Zapier/Make/n8n "Webhooks" step in between) at the URL.
- **Meta Lead Ads** → Zapier/Make has a native "Meta Lead Ads: New Lead"
  trigger → "Webhooks: POST" action pointed at your URL. No code.
- **Google Local Services Ads (LSA)** → same pattern via Zapier's Google
  LSA integration, or their leads-export email parsed by a Zapier email
  parser into a webhook.
- **Missed calls** → in the Twilio Console, set the phone number's
  "Call Status Changed" webhook to
  `https://your-app/webhook/missed-call?key=<your WEBHOOK_API_KEY>`
  (query param, since Twilio's callback can't set custom headers).
- **Any CRM or spreadsheet** → n8n/Make/Zapier can watch almost anything
  (a new row, a new CRM record) and fire the same webhook.

Going live checklist once you have a paying client:
- [ ] `DEMO_MODE=false`
- [ ] Real `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_PHONE`
- [ ] Real `SENDGRID_API_KEY` / `FROM_EMAIL` (verified sender in SendGrid)
- [ ] Real `BOOKING_LINK` (their actual Calendly/Acuity/etc.)
- [ ] Real `OWNER_EMAIL` / `OWNER_PHONE` / `SLACK_WEBHOOK_URL` (at least one)
- [ ] `PUBLIC_BASE_URL` set to the real deployed URL
- [ ] `WEBHOOK_API_KEY` changed from the default
- [ ] `DASHBOARD_PASSWORD` set

The app logs a warning on startup if you go live with the default API key
or a still-localhost `PUBLIC_BASE_URL`, so check the logs after deploying.

---

## 5. Running a live demo on a call

1. Deploy it (section 3) with `BUSINESS_NAME` set to *their* business name —
   seeing their own name on the dashboard lands better than a generic one.
2. Before the call: `POST /admin/reset?key=<your key>` to clear any old
   demo leads so the screen is empty when they join.
3. Optional: temporarily set `REMINDER_DELAY_SECONDS=20` before the call so
   they see the "owner reminder" fire live instead of waiting 10 minutes.
4. Share your screen on the dashboard. Say something like: *"This is what
   happens the second a lead hits your website form."* Click **Simulate new
   lead**. Point at the timer ticking up in real time, then the SMS/email
   text appearing in the activity feed a second later, then the 47-hour vs
   your-time comparison at the top.
5. Click a lead's **View** to show the full timeline (received → texted →
   emailed → owner alerted), then click **Mark booked** to show the
   conversion tracking.
6. Close with the numbers, not features: *"Right now your average lead
   waits [X hours] for a reply. This gets it under a minute, and whoever
   replies first wins the deal about 78% of the time."*

---

## 6. Selling this (LinkedIn / Upwork / Fiverr)

Pricing that fits a solo build of this exact system:
- One-time build + setup: **$750–$2,500**
- Ongoing hosting/maintenance retainer: **$150–$400/month**

**Best channel:** cold LinkedIn/email — owners in this space (real estate,
home services, law firms, med spas, agencies buying leads) rarely search
"speed to lead" by name, so you go to them instead of waiting on Fiverr/Upwork
search traffic. Post the build on Fiverr/Upwork too as a secondary channel,
but expect outbound to convert faster for this specific offer.

**Cold LinkedIn opener** (keep under ~125 words, always queue 3–4
follow-ups — most replies come from the 2nd–4th message, not the first):

> Hi [name] — noticed [specific thing, e.g. your site sends leads to a
> general inbox]. I build systems that text/call new leads within 60
> seconds of them coming in — one business I worked with went from a
> 4-hour average response to under 2 minutes. Worth a 10-minute look at
> what that'd take for [company]?

Swap in a live link to your deployed demo (with a fake `BUSINESS_NAME`, or
better — their actual name, via `PUBLIC_BASE_URL` + `?business=` override
already supported by the dashboard) instead of a screenshot. Letting them
click "Simulate new lead" themselves closes faster than any screenshot will.

**First real client:** build it free or near-free for one actual business.
That single free build becomes a demo link, a case study, and a testimonial
at once — worth more than any cold pitch on its own.

---

## 7. Known limits (be upfront about these with a client)

- SQLite is fine for one business's lead volume; if a client wants
  multi-tenant (many businesses on one instance), swap to Postgres — the
  `database.py` functions are the only thing that would need to change.
- Most PaaS free tiers (Render free, etc.) wipe local disk on redeploy —
  the SQLite file goes with it. Fine for a demo; for a paying client on a
  free tier, either upgrade to a paid instance with a persistent disk, or
  swap to a hosted Postgres (Render/Railway both offer a free Postgres
  instance you could point this at later).
- No rate limiting on the webhook endpoints yet — low risk behind a secret
  API key, but worth adding (e.g. `slowapi`) before high lead volume.
- The `/book/{id}` click is used as the "booked" proxy. If you want it tied
  to an actual calendar booking event instead of just a link click, that
  needs a Calendly/Acuity webhook wired back in — happy to add that when
  you're ready to build it for a real client.
