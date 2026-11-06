
import numpy as np
import pandas as pd
from pathlib import Path


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

RANDOM_SEED = 42
TOTAL_TRANSACTIONS = 5000
NORMAL_TRANSACTIONS = 4800
SUSPICIOUS_TRANSACTIONS = 200

rng = np.random.default_rng(RANDOM_SEED)

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "transactions.csv"


# --------------------------------------------------
# 2. MASTER DATA
# --------------------------------------------------

customers = [f"CUST{i:04d}" for i in range(1, 1001)]
devices = [f"DEV{i:04d}" for i in range(1, 301)]
merchants = [f"MERCH{i:03d}" for i in range(1, 101)]

# Reserved documentation IP ranges for synthetic data
ip_addresses = [
    f"192.0.2.{i}" for i in range(1, 255)
]

channels = ["MOBILE", "WEB", "ATM"]
transaction_types = ["PAYMENT", "TRANSFER"]


# --------------------------------------------------
# 3. GENERATE NORMAL TRANSACTIONS
# --------------------------------------------------

normal_data = []

start_date = pd.Timestamp("2026-01-01")

for i in range(NORMAL_TRANSACTIONS):

    transaction = {
        "transaction_id": f"TXN{i + 1:06d}",
        "customer_id": rng.choice(customers),
        "amount": round(float(rng.lognormal(7.5, 0.8)), 2),
        "timestamp": start_date
        + pd.Timedelta(
            minutes=int(rng.integers(0, 30 * 24 * 60))
        ),
        "device_id": rng.choice(devices),
        "ip_address": rng.choice(ip_addresses),
        "merchant_id": rng.choice(merchants),
        "transaction_type": rng.choice(transaction_types),
        "channel": rng.choice(channels),
        "status": rng.choice(
            ["SUCCESS", "SUCCESS", "SUCCESS", "FAILED"]
        ),
        "is_fraud": 0,
        "pattern_type": "NORMAL"
    }

    normal_data.append(transaction)


# --------------------------------------------------
# 4. GENERATE SUSPICIOUS TRANSACTION CLUSTERS
# --------------------------------------------------

suspicious_data = []

transaction_counter = NORMAL_TRANSACTIONS + 1

for cluster in range(4):

    # Five customers share a device and IP
    cluster_customers = [
        f"CLUSTER{cluster + 1}_CUST{i}"
        for i in range(1, 6)
    ]

    shared_device = f"SHARED_DEV_{cluster + 1}"
    shared_ip = f"203.0.113.{cluster + 1}"
    shared_merchant = f"MERCH{cluster + 1:03d}"

    cluster_start = start_date + pd.Timedelta(
        days=cluster * 5
    )

    for i in range(50):

        customer = cluster_customers[i % 5]

        timestamp = cluster_start + pd.Timedelta(
            minutes=int(rng.integers(0, 60))
        )

        amount = round(
            float(rng.uniform(25000, 100000)), 2
        )

        # Add high-velocity and shared-resource patterns
        if i < 20:
            pattern = "SHARED_DEVICE_IP_MERCHANT_CLUSTER"
        elif i < 35:
            pattern = "HIGH_VELOCITY"
        else:
            pattern = "UNUSUAL_HIGH_VALUE"

        suspicious_data.append({
            "transaction_id": f"TXN{transaction_counter:06d}",
            "customer_id": customer,
            "amount": amount,
            "timestamp": timestamp,
            "device_id": shared_device,
            "ip_address": shared_ip,
            "merchant_id": shared_merchant,
            "transaction_type": "TRANSFER",
            "channel": "MOBILE",
            "status": "SUCCESS",
            "is_fraud": 1,
            "pattern_type": pattern
        })

        transaction_counter += 1


# --------------------------------------------------
# 5. COMBINE AND SHUFFLE DATA
# --------------------------------------------------

all_transactions = normal_data + suspicious_data

df = pd.DataFrame(all_transactions)

df["timestamp"] = pd.to_datetime(df["timestamp"])

df = df.sample(
    frac=1,
    random_state=RANDOM_SEED
).reset_index(drop=True)


# --------------------------------------------------
# 6. SAVE DATASET
# --------------------------------------------------

df.to_csv(OUTPUT_FILE, index=False)


# --------------------------------------------------
# 7. DISPLAY DATASET SUMMARY
# --------------------------------------------------

print("\nBANKING TRANSACTION DATASET GENERATED")
print("-" * 45)

print(f"Total transactions: {len(df)}")

print("\nFraud label distribution:")
print(df["is_fraud"].value_counts())

print("\nPattern distribution:")
print(df["pattern_type"].value_counts())

print("\nDataset columns:")
print(df.columns.tolist())

print("\nFirst 5 records:")
print(df.head())

print("\nDataset saved successfully:")
print(OUTPUT_FILE)
