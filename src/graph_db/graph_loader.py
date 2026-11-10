
import os
import pandas as pd

from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Database configuration
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

CSV_PATH = Path("data/raw/transactions.csv")


class Neo4jGraphLoader:

    def __init__(self):
        if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
            raise ValueError("Missing Neo4j environment variables.")

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def prepare_data(self):
        if not CSV_PATH.exists():
            raise FileNotFoundError(f"Dataset not found: {CSV_PATH}")

        df = pd.read_csv(CSV_PATH)

        required_columns = [
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

        missing = set(required_columns) - set(df.columns)

        if missing:
            raise ValueError(f"Missing columns: {missing}")

        df = df.where(pd.notna(df), None)

        df["timestamp"] = pd.to_datetime(
            df["timestamp"], errors="coerce", utc=True
        ).astype(str)

        rows = df[required_columns].to_dict("records")

        return rows

    @staticmethod
    def load_batch(tx, rows):

        query = """
        UNWIND $rows AS row

        MERGE (c:Customer {customer_id: row.customer_id})

        MERGE (t:Transaction {
            transaction_id: row.transaction_id
        })

        SET t.amount = row.amount,
            t.timestamp = row.timestamp,
            t.transaction_type = row.transaction_type,
            t.channel = row.channel,
            t.status = row.status,
            t.is_fraud = row.is_fraud,
            t.pattern_type = row.pattern_type

        MERGE (c)-[:INITIATED]->(t)

        MERGE (m:Merchant {merchant_id: row.merchant_id})

        MERGE (t)-[:PAID_TO]->(m)

        MERGE (d:Device {device_id: row.device_id})

        MERGE (t)-[:USED_DEVICE]->(d)

        MERGE (ip:IPAddress {ip_address: row.ip_address})

        MERGE (t)-[:ORIGINATED_FROM]->(ip)
        """

        tx.run(query, rows=rows)

    def load_transactions(self, batch_size=500):

        rows = self.prepare_data()

        print(f"Total transactions found: {len(rows)}")

        with self.driver.session(database=NEO4J_DATABASE) as session:

            for start in range(0, len(rows), batch_size):

                batch = rows[start:start + batch_size]

                session.execute_write(
                    self.load_batch,
                    batch
                )

                print(
                    f"Loaded {min(start + batch_size, len(rows))}"
                    f"/{len(rows)} transactions"
                )

        print("Neo4j graph loading completed successfully!")


if __name__ == "__main__":

    loader = Neo4jGraphLoader()

    try:
        loader.load_transactions()

    finally:
        loader.close()
