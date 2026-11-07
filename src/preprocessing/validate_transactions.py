
import pandas as pd
from pathlib import Path

FILE_PATH = Path("data/raw/transactions.csv")

REQUIRED_COLUMNS = [
    "transaction_id",
    "customer_id",
    "amount",
    "timestamp",
    "device_id",
    "ip_address",
    "merchant_id",
    "transaction_type",
    "channel",
    "status",
    "is_fraud",
    "pattern_type"
]


def validate_transactions():

    df = pd.read_csv(FILE_PATH)

    print("BANKING DATA VALIDATION")
    print("-" * 35)

    # Check required columns
    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
    assert not missing_columns, f"Missing columns: {missing_columns}"

    # Check duplicate transaction IDs
    assert df["transaction_id"].is_unique, "Duplicate transaction IDs found"

    # Check missing values
    assert not df[REQUIRED_COLUMNS].isnull().any().any(), "Missing values found"

    # Check transaction amounts
    assert (df["amount"] > 0).all(), "Invalid transaction amounts"

    # Check fraud labels
    assert set(df["is_fraud"].unique()).issubset({0, 1}), "Invalid fraud labels"

    print("Total records:", len(df))
    print("Unique transactions:", df["transaction_id"].nunique())
    print("Normal transactions:", (df["is_fraud"] == 0).sum())
    print("Suspicious transactions:", (df["is_fraud"] == 1).sum())
    print("\nAll validation checks passed!")


if __name__ == "__main__":
    validate_transactions()
