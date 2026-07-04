import time
import random
from datetime import datetime, timezone, timedelta
import database
from demo_data import random_demo_lead

database.init_db()

# Generate 8 random leads over the past 24 hours
now = datetime.now(timezone.utc)

for i in range(8):
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
    
    # Randomly respond to some leads
    if random.random() > 0.3:
        response_time = random.uniform(5, 300) # responded in 5s to 5 mins
        database.mark_contacted(lead_id, response_time)
        database.add_event(lead_id, "sms_sent_demo", f"Sent automated SMS reply to {lead_data['phone']}")
        
        # Randomly book some leads
        if random.random() > 0.5:
            database.update_status(lead_id, "Booked")
            database.add_event(lead_id, "link_clicked", "Lead clicked booking link and scheduled an appointment")

print("Successfully seeded dashboard with dummy data.")
