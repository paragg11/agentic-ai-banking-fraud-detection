
import pandas as pd
from pathlib import Path


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

INPUT_FILE = Path("data/raw/transactions.csv")

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 2. LOAD TRANSACTION DATA
# --------------------------------------------------

def load_transactions():

    df = pd.read_csv(INPUT_FILE)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["amount"] = pd.to_numeric(df["amount"])

    print("Transaction dataset loaded successfully.")
    print("Total transactions:", len(df))

    return df


# --------------------------------------------------
# 3. ANALYZE TRANSACTION AMOUNTS
# --------------------------------------------------

def analyze_transaction_amounts(df):

    print("\nTRANSACTION AMOUNT ANALYSIS")
    print("-" * 40)

    print("Average amount:", round(df["amount"].mean(), 2))
    print("Maximum amount:", round(df["amount"].max(), 2))
    print("Minimum amount:", round(df["amount"].min(), 2))

    # Use the 99th percentile as an analytical threshold
    threshold = df["amount"].quantile(0.99)

    high_value = df[df["amount"] > threshold].copy()

    print("99th percentile threshold:", round(threshold, 2))
    print("High-value transactions:", len(high_value))

    return high_value


# --------------------------------------------------
# 4. IDENTIFY SHARED DEVICES
# --------------------------------------------------

def detect_shared_devices(df):

    print("\nSHARED DEVICE ANALYSIS")
    print("-" * 40)

    device_analysis = (
        df.groupby("device_id")
        .agg(
            transaction_count=("transaction_id", "count"),
            customer_count=("customer_id", "nunique"),
            fraud_count=("is_fraud", "sum")
        )
        .reset_index()
    )

    shared_devices = device_analysis[
        device_analysis["customer_count"] > 1
    ].sort_values(
        "customer_count",
        ascending=False
    )

    print("Shared devices identified:", len(shared_devices))

    return shared_devices


# --------------------------------------------------
# 5. IDENTIFY SHARED IP ADDRESSES
# --------------------------------------------------

def detect_shared_ips(df):

    print("\nSHARED IP ANALYSIS")
    print("-" * 40)

    ip_analysis = (
        df.groupby("ip_address")
        .agg(
            transaction_count=("transaction_id", "count"),
            customer_count=("customer_id", "nunique"),
            fraud_count=("is_fraud", "sum")
        )
        .reset_index()
    )

    shared_ips = ip_analysis[
        ip_analysis["customer_count"] > 1
    ].sort_values(
        "customer_count",
        ascending=False
    )

    print("Shared IP addresses identified:", len(shared_ips))

    return shared_ips


# --------------------------------------------------
# 6. IDENTIFY MERCHANT CLUSTERS
# --------------------------------------------------

def detect_merchant_clusters(df):

    print("\nMERCHANT CLUSTER ANALYSIS")
    print("-" * 40)

    merchant_analysis = (
        df.groupby("merchant_id")
        .agg(
            transaction_count=("transaction_id", "count"),
            customer_count=("customer_id", "nunique"),
            total_amount=("amount", "sum"),
            fraud_count=("is_fraud", "sum")
        )
        .reset_index()
    )

    merchant_clusters = merchant_analysis[
        (merchant_analysis["customer_count"] > 1)
        & (merchant_analysis["fraud_count"] > 0)
    ].sort_values(
        "fraud_count",
        ascending=False
    )

    print("Merchants with simulated suspicious activity:",
          len(merchant_clusters))

    return merchant_clusters


# --------------------------------------------------
# 7. DETECT HIGH-VELOCITY TRANSACTIONS
# --------------------------------------------------

def detect_high_velocity(df):

    print("\nTRANSACTION VELOCITY ANALYSIS")
    print("-" * 40)

    # Count transactions per customer within each 10-minute window
    df = df.copy()

    df["time_window"] = df["timestamp"].dt.floor("10min")

    velocity = (
        df.groupby(["customer_id", "time_window"])
        .agg(
            transaction_count=("transaction_id", "count"),
            total_amount=("amount", "sum")
        )
        .reset_index()
    )

    high_velocity = velocity[
        velocity["transaction_count"] >= 3
    ].sort_values(
        "transaction_count",
        ascending=False
    )

    print("High-velocity windows identified:", len(high_velocity))

    return high_velocity


# --------------------------------------------------
# 8. GENERATE ANALYTICS SUMMARY
# --------------------------------------------------

def generate_summary(
    df,
    high_value,
    shared_devices,
    shared_ips,
    merchant_clusters,
    high_velocity
):

    summary = {
        "total_transactions": int(len(df)),
        "normal_transactions": int((df["is_fraud"] == 0).sum()),
        "simulated_suspicious_transactions": int(
            (df["is_fraud"] == 1).sum()
        ),
        "high_value_transactions": int(len(high_value)),
        "shared_devices": int(len(shared_devices)),
        "shared_ip_addresses": int(len(shared_ips)),
        "suspicious_merchant_clusters": int(len(merchant_clusters)),
        "high_velocity_windows": int(len(high_velocity))
    }

    summary_df = pd.DataFrame(
        list(summary.items()),
        columns=["metric", "value"]
    )

    summary_file = OUTPUT_DIR / "fraud_analytics_summary.csv"

    summary_df.to_csv(summary_file, index=False)

    print("\nFINAL FRAUD ANALYTICS SUMMARY")
    print("-" * 45)

    for metric, value in summary.items():
        print(f"{metric}: {value}")

    print("\nSummary saved to:", summary_file)


# --------------------------------------------------
# 9. MAIN EXECUTION
# --------------------------------------------------

def main():

    df = load_transactions()

    high_value = analyze_transaction_amounts(df)

    shared_devices = detect_shared_devices(df)

    shared_ips = detect_shared_ips(df)

    merchant_clusters = detect_merchant_clusters(df)

    high_velocity = detect_high_velocity(df)

    generate_summary(
        df,
        high_value,
        shared_devices,
        shared_ips,
        merchant_clusters,
        high_velocity
    )

    print("\nFraud analytics engine executed successfully!")


if __name__ == "__main__":
    main()
