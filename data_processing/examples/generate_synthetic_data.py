"""Generate synthetic data for demonstration.

This script generates realistic synthetic data that demonstrates:
- PII detection and anonymization
- Large-scale data processing (configurable size)
- Text clustering and embeddings
- Data quality issues
"""
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import polars as pl
from faker import Faker


fake = Faker()
Faker.seed(42)
random.seed(42)


class SyntheticDataGenerator:
    """Generates realistic synthetic data for demonstrations."""

    def __init__(self, num_records: int = 100_000):
        self.num_records = num_records

    def generate_customer_data(self) -> pl.DataFrame:
        """Generate customer interaction data with PII."""
        data = {
            "id": list(range(self.num_records)),
            "timestamp": [
                (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat()
                for _ in range(self.num_records)
            ],
            "customer_name": [fake.name() for _ in range(self.num_records)],
            "email": [fake.email() for _ in range(self.num_records)],
            "phone": [fake.phone_number() for _ in range(self.num_records)],
            "message": [self._generate_message() for _ in range(self.num_records)],
            "category": [
                random.choice(["billing", "technical", "account", "general", "complaint"])
                for _ in range(self.num_records)
            ],
            "sentiment": [
                random.choice(["positive", "neutral", "negative"])
                for _ in range(self.num_records)
            ],
            "priority": [random.randint(1, 5) for _ in range(self.num_records)],
            "resolved": [random.choice([True, False]) for _ in range(self.num_records)],
        }

        # Add some data quality issues
        # 1. Introduce some nulls
        null_indices = random.sample(range(self.num_records), self.num_records // 20)
        for idx in null_indices:
            data["phone"][idx] = None

        # 2. Introduce some duplicates
        dup_indices = random.sample(range(self.num_records), self.num_records // 50)
        for i, idx in enumerate(dup_indices):
            if i + 1 < len(dup_indices):
                data["message"][idx] = data["message"][dup_indices[i + 1]]

        return pl.DataFrame(data)

    def _generate_message(self) -> str:
        """Generate a realistic customer message."""
        templates = [
            "I'm having trouble with {issue}. My account number is {account}. Please help!",
            "Can you help me with {issue}? I've been trying to resolve this for days.",
            "I'm very satisfied with {feature}! Great job!",
            "The {issue} is not working properly. Need assistance ASAP.",
            "I would like to inquire about {feature}. Can you provide more information?",
            "There's a problem with my billing. I was charged ${amount} but expected ${amount2}.",
            "Your service is excellent! I especially like {feature}.",
            "I need to update my information. My new phone is {phone}.",
            "Can someone call me at {phone} to discuss {issue}?",
            "I'm experiencing {issue} since {date}. This is urgent!",
        ]

        issues = [
            "login",
            "payment processing",
            "account access",
            "data sync",
            "password reset",
            "subscription renewal",
        ]

        features = [
            "the new dashboard",
            "the mobile app",
            "customer support",
            "the reporting feature",
            "the API integration",
        ]

        template = random.choice(templates)
        message = template.format(
            issue=random.choice(issues),
            feature=random.choice(features),
            account=''.join(random.choices(string.digits, k=10)),
            amount=random.randint(10, 500),
            amount2=random.randint(10, 500),
            phone=fake.phone_number(),
            date=fake.date_this_year().isoformat(),
        )

        return message

    def generate_usage_logs(self) -> pl.DataFrame:
        """Generate API usage logs."""
        actions = ["GET /api/users", "POST /api/data", "PUT /api/update", "DELETE /api/resource"]
        statuses = [200, 201, 400, 401, 403, 404, 500]
        status_weights = [60, 10, 10, 5, 5, 5, 5]

        data = {
            "timestamp": [
                (datetime.now() - timedelta(seconds=random.randint(0, 86400 * 30))).isoformat()
                for _ in range(self.num_records)
            ],
            "user_id": [f"user_{random.randint(1, 10000)}" for _ in range(self.num_records)],
            "ip_address": [fake.ipv4() for _ in range(self.num_records)],
            "action": [random.choice(actions) for _ in range(self.num_records)],
            "status_code": random.choices(statuses, weights=status_weights, k=self.num_records),
            "response_time_ms": [random.randint(10, 5000) for _ in range(self.num_records)],
            "bytes_transferred": [random.randint(100, 1000000) for _ in range(self.num_records)],
        }

        return pl.DataFrame(data)


def main():
    """Generate demonstration datasets."""
    output_dir = Path("demo_data")
    output_dir.mkdir(exist_ok=True)

    print("Generating synthetic data for demonstration...")
    print(f"Output directory: {output_dir.absolute()}\n")

    # Generate datasets of different sizes for testing
    sizes = {
        "small": 10_000,      # ~1 MB
        "medium": 100_000,    # ~10 MB
        "large": 1_000_000,   # ~100 MB
    }

    for size_name, num_records in sizes.items():
        print(f"Generating {size_name} dataset ({num_records:,} records)...")

        generator = SyntheticDataGenerator(num_records)

        # Customer data
        customer_df = generator.generate_customer_data()
        customer_file = output_dir / f"customers_{size_name}.parquet"
        customer_df.write_parquet(customer_file, compression="zstd")
        file_size_mb = customer_file.stat().st_size / 1024 / 1024
        print(f"  ✓ Customers: {customer_file} ({file_size_mb:.1f} MB)")

        # Usage logs
        usage_df = generator.generate_usage_logs()
        usage_file = output_dir / f"usage_logs_{size_name}.parquet"
        usage_df.write_parquet(usage_file, compression="zstd")
        file_size_mb = usage_file.stat().st_size / 1024 / 1024
        print(f"  ✓ Usage logs: {usage_file} ({file_size_mb:.1f} MB)\n")

    print("✓ Synthetic data generation complete!")
    print(f"\nTo process the data, run:")
    print(f"  python -m data_processing process demo_data/customers_large.parquet output/ --enable-pii")


if __name__ == "__main__":
    # Install faker if needed
    try:
        from faker import Faker
    except ImportError:
        print("Installing faker...")
        import subprocess
        subprocess.run(["pip", "install", "faker"], check=True)
        from faker import Faker

    main()
