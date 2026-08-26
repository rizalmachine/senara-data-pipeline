"""Synthetic WhatsApp-style conversation generator.

Produces raw inbound/outbound message rows shaped like a real CRM export (From/To
number pairs, not pre-resolved direction/customer columns) so pipeline.transform's
direction-detection logic has real work to do. Response-time gaps follow a
log-normal distribution during office hours, with an instant bot auto-reply +
delayed human follow-up outside them -- this is what exercises the response-time
calc and the out-of-office branch downstream.
"""
import random
from datetime import datetime, timedelta

import pandas as pd

from pipeline import config
from data_gen.generate_reference import OOH_AUTOREPLY

CONTACT_REASONS = ["new_lead", "follow_up", "complaint", "general"]
REASON_WEIGHTS = [0.35, 0.30, 0.10, 0.25]


def _fake_customer_phone(rng, used):
    while True:
        candidate = "628" + "".join(rng.choice("123456789") for _ in range(9))
        if candidate not in used and candidate not in config.BRAND_NUMBERS:
            used.add(candidate)
            return candidate


def _response_delay_minutes(rng):
    # log-normal, median ~4 min, occasional long tail
    return rng.lognormvariate(1.4, 0.9)


def generate(customers=config.CUSTOMERS, days=config.DAYS, seed=config.SEED, agents=None):
    rng = random.Random(seed)
    end = datetime.now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)

    agent_names = list(agents["agent_name"]) if agents is not None else ["Agent A", "Agent B"]
    used_phones = set()
    rows = []
    message_id = 1

    for _ in range(customers):
        customer_phone = _fake_customer_phone(rng, used_phones)
        brand_number = rng.choice(sorted(config.BRAND_NUMBERS))
        contact_day = start + timedelta(seconds=rng.randint(0, int((end - start).total_seconds())))

        # 1-2 inbound messages same day, so downstream dedup has something to do.
        num_inbound = 2 if rng.random() < 0.3 else 1
        for i in range(num_inbound):
            sent_at = contact_day + timedelta(minutes=rng.randint(0, 90) * i)
            reason = rng.choices(CONTACT_REASONS, weights=REASON_WEIGHTS, k=1)[0]

            rows.append({
                "message_id": message_id,
                "from_number": customer_phone,
                "to_number": brand_number,
                "sent_at": sent_at,
                "agent_name": None,
                "contact_reason": reason,
                "body": None,
            })
            message_id += 1

            in_office_hours = config.OFFICE_HOURS_START <= sent_at.hour < config.OFFICE_HOURS_END
            if in_office_hours:
                reply_at = sent_at + timedelta(minutes=_response_delay_minutes(rng))
                rows.append({
                    "message_id": message_id,
                    "from_number": brand_number,
                    "to_number": customer_phone,
                    "sent_at": reply_at,
                    "agent_name": rng.choice(agent_names),
                    "contact_reason": None,
                    "body": None,
                })
                message_id += 1
            else:
                # Instant bot auto-reply, then a real human follow-up next morning.
                bot_reply_at = sent_at + timedelta(seconds=rng.randint(5, 40))
                rows.append({
                    "message_id": message_id,
                    "from_number": brand_number,
                    "to_number": customer_phone,
                    "sent_at": bot_reply_at,
                    "agent_name": None,
                    "contact_reason": None,
                    "body": OOH_AUTOREPLY,
                })
                message_id += 1

                next_morning = (sent_at + timedelta(days=1)).replace(
                    hour=config.OFFICE_HOURS_START, minute=rng.randint(0, 30), second=0
                )
                rows.append({
                    "message_id": message_id,
                    "from_number": brand_number,
                    "to_number": customer_phone,
                    "sent_at": next_morning,
                    "agent_name": rng.choice(agent_names),
                    "contact_reason": None,
                    "body": None,
                })
                message_id += 1

    df = pd.DataFrame(rows).sort_values("sent_at").reset_index(drop=True)
    df["message_id"] = range(1, len(df) + 1)
    return df
