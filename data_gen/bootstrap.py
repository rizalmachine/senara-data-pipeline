"""Entry point: `python -m data_gen.bootstrap [--customers N] [--days N] [--seed N] [--force]`

Generates synthetic reference + conversation data and drops it into data/incoming/,
simulating a file landing from an external system -- pipeline.extract then loads it
from there, the same shape as the real ingestion step.
"""
import argparse

from pipeline import config
from data_gen.generate_reference import generate_agents, generate_prior_contacts
from data_gen.generate_conversations import generate as generate_conversations


def bootstrap(customers=config.CUSTOMERS, days=config.DAYS, seed=config.SEED, force=False):
    config.INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    conversations_path = config.INCOMING_DIR / "conversations.csv"
    agents_path = config.INCOMING_DIR / "ref_agents.csv"
    prior_contacts_path = config.INCOMING_DIR / "ref_prior_contacts.csv"

    if conversations_path.exists() and not force:
        print(f"[SKIP] {conversations_path} already exists (use --force to regenerate)")
        return

    agents_df = generate_agents(seed=seed)
    conversations_df = generate_conversations(customers=customers, days=days, seed=seed, agents=agents_df)
    customer_phones = conversations_df.loc[
        ~conversations_df["from_number"].isin(config.BRAND_NUMBERS), "from_number"
    ].unique()
    prior_contacts_df = generate_prior_contacts(customer_phones, seed=seed)

    agents_df.to_csv(agents_path, index=False)
    prior_contacts_df.to_csv(prior_contacts_path, index=False)
    conversations_df.to_csv(conversations_path, index=False)

    print(f"[OK] {len(agents_df)} agents -> {agents_path}")
    print(f"[OK] {len(prior_contacts_df)} prior contacts -> {prior_contacts_path}")
    print(f"[OK] {len(conversations_df)} messages ({len(customer_phones)} customers) -> {conversations_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic demo data")
    parser.add_argument("--customers", type=int, default=config.CUSTOMERS)
    parser.add_argument("--days", type=int, default=config.DAYS)
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    bootstrap(customers=args.customers, days=args.days, seed=args.seed, force=args.force)


if __name__ == "__main__":
    main()
