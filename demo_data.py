"""Fake-but-realistic leads for the dashboard's 'Simulate New Lead' button.

Phone numbers use the 555 prefix, which is reserved for fictional use in
North America - never a real subscriber, even by accident.
"""
import random

_DEMO_LEADS = [
    {"name": "Sarah Mitchell", "source": "Facebook Ads", "message": "Interested in a free consultation"},
    {"name": "James Okafor", "source": "Website Form", "message": "Do you have availability this week?"},
    {"name": "Priya Nair", "source": "Google LSA", "message": "Looking for pricing info"},
    {"name": "Carlos Rivera", "source": "Missed Call", "message": None},
    {"name": "Emily Chen", "source": "Website Form", "message": "Can someone call me back today?"},
    {"name": "Ahmed Raza", "source": "Facebook Ads", "message": "Saw your ad, want to know more"},
    {"name": "Olivia Bennett", "source": "Referral", "message": "My friend recommended you"},
    {"name": "Daniel Kim", "source": "Google LSA", "message": "Need a quote ASAP"},
]

def random_demo_lead() -> dict:
    base = random.choice(_DEMO_LEADS)
    name = base["name"]
    slug = name.lower().replace(" ", ".")
    return {
        "name": name,
        "email": f"{slug}{random.randint(1, 999)}@example.com",
        "phone": f"+1555{random.randint(1000000, 9999999)}",
        "source": base["source"],
        "message": base["message"],
    }
