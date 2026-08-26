"""Synthetic reference/lookup data: CS agent roster and the prior-contact snapshot
that silver transform diffs against to flag new-vs-returning customers.
"""
import random

import pandas as pd
from faker import Faker

OOH_AUTOREPLY = (
    "Terima kasih telah menghubungi kami di luar jam operasional (08.00-23.00). "
    "Tim kami akan membalas secepatnya. / Thanks for reaching out outside business "
    "hours (08:00-23:00). Our team will reply as soon as possible."
)


def generate_agents(n=18, seed=42) -> pd.DataFrame:
    Faker.seed(seed)
    fake = Faker("id_ID")
    names = {fake.name() for _ in range(n)}
    while len(names) < n:
        names.add(fake.name())
    return pd.DataFrame({"agent_name": sorted(names)})


def generate_prior_contacts(customer_phones, fraction=0.25, seed=42) -> pd.DataFrame:
    """A subset of customers treated as already-known before the generated window --
    lets new-contact detection have something real to diff against."""
    rng = random.Random(seed)
    k = int(len(customer_phones) * fraction)
    prior = rng.sample(list(customer_phones), k) if k else []
    return pd.DataFrame({"customer_phone": prior})
