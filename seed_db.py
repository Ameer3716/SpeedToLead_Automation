import random
from datetime import datetime, timezone, timedelta
import database
from demo_data import random_demo_lead


def seed(count: int = 8) -> int:
    """Populates the dashboard with realistic-looking leads spread over the
    past 24 hours. Used by both this standalone script and POST /admin/seed
    (so it can be triggered on a live deployment with no shell access)."""
    database.init_db()
    now = datetime.now(timezone.utc)
    created = 0

    for _ in range(count):
        lead_data = random_demo_lead()
        created_at = now - timedelta(hours=random.uniform(0.5, 23.0))
        lead_id = database.create_lead(
            name=lead_data["name"],
            email=lead_data["email"],
            phone=lead_data["phone"],
            source=lead_data["source"],
            message=lead_data["message"],
            created_at=created_at
        )
        created += 1

        # Randomly respond to some leads
        if random.random() > 0.3:
            response_time = random.uniform(5, 300)  # responded in 5s to 5 mins
            database.mark_contacted(lead_id, response_time)
            database.add_event(lead_id, "sms_sent_demo", f"Sent automated SMS reply to {lead_data['phone']}")

            # Randomly book some leads
            if random.random() > 0.5:
                database.update_status(lead_id, "Booked")
                database.add_event(lead_id, "link_clicked", "Lead clicked booking link and scheduled an appointment")

    return created


if __name__ == "__main__":
    n = seed()
    print(f"Successfully seeded dashboard with {n} leads.")

