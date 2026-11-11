
import csv
from pathlib import Path

from src.graph_db.neo4j_connection import Neo4jConnection


class RiskScoringEngine:

    # ---------------------------------------
    # 1. CONFIGURATION
    # ---------------------------------------

    HIGH_VALUE_THRESHOLD = 50000

    SHARED_DEVICE_THRESHOLD = 3
    SHARED_IP_THRESHOLD = 3
    VELOCITY_THRESHOLD = 5

    RISK_WEIGHTS = {
        "high_value": 25,
        "shared_device": 25,
        "shared_ip": 20,
        "high_velocity": 20
    }

    def __init__(self):

        self.db = Neo4jConnection()
        self.driver = self.db.driver

        self.output_dir = Path("data/processed")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print("Risk Scoring Engine initialized.")

    # ---------------------------------------
    # 2. FETCH TRANSACTION RISK SIGNALS
    # ---------------------------------------

    def fetch_transaction_signals(self):

        query = """
        MATCH (t:Transaction)

        OPTIONAL MATCH (c:Customer)-[:INITIATED]->(t)
        OPTIONAL MATCH (t)-[:USED_DEVICE]->(d:Device)
        OPTIONAL MATCH (t)-[:ORIGINATED_FROM]->(ip:IPAddress)

        WITH t, c, d, ip

        CALL {
            WITH d
            OPTIONAL MATCH
            (other_c:Customer)-[:INITIATED]->
            (:Transaction)-[:USED_DEVICE]->(d)

            RETURN count(DISTINCT other_c)
            AS device_customer_count
        }

        CALL {
            WITH ip
            OPTIONAL MATCH
            (other_c:Customer)-[:INITIATED]->
            (:Transaction)-[:ORIGINATED_FROM]->(ip)

            RETURN count(DISTINCT other_c)
            AS ip_customer_count
        }

        CALL {
            WITH c, t

            OPTIONAL MATCH
            (c)-[:INITIATED]->(recent:Transaction)

            WHERE datetime(
                replace(toString(recent.timestamp), ' ', 'T')
            )
            >=datetime(
                replace(toString(t.timestamp), ' ', 'T')
            ) - duration('PT10M')

            AND datetime(
                replace(toString(recent.timestamp), ' ', 'T')
            )
            <=
            datetime(
                replace(toString(t.timestamp), ' ', 'T')
            )

            RETURN count(DISTINCT recent)
            AS transaction_count_10m
        }

        RETURN
            t.transaction_id AS transaction_id,
            t.customer_id AS customer_id,
            t.amount AS amount,
            t.timestamp AS timestamp,

            device_customer_count,
            ip_customer_count,
            transaction_count_10m

        ORDER BY transaction_id
        """

        with self.driver.session() as session:

            result = session.run(query)

            transactions = [
                record.data()
                for record in result
            ]

        print(
            "Transactions fetched:",
            len(transactions)
        )

        return transactions

    # ---------------------------------------
    # 3. CALCULATE RISK SCORE
    # ---------------------------------------

    def calculate_risk_score(self, transaction):

        score = 0
        reasons = []

        amount = float(transaction.get("amount") or 0)

        device_count = int(
            transaction.get("device_customer_count") or 0
        )

        ip_count = int(
            transaction.get("ip_customer_count") or 0
        )

        velocity = int(
            transaction.get("transaction_count_10m") or 0
        )

        # High-value transaction

        if amount >= self.HIGH_VALUE_THRESHOLD:

            score += self.RISK_WEIGHTS["high_value"]

            reasons.append(
                "High-value transaction"
            )

        # Shared device detection

        if device_count >= self.SHARED_DEVICE_THRESHOLD:

            score += self.RISK_WEIGHTS["shared_device"]

            reasons.append(
                "Device shared by multiple customers"
            )

        # Shared IP detection

        if ip_count >= self.SHARED_IP_THRESHOLD:

            score += self.RISK_WEIGHTS["shared_ip"]

            reasons.append(
                "IP address shared by multiple customers"
            )

        # Transaction velocity detection

        if velocity >= self.VELOCITY_THRESHOLD:

            score += self.RISK_WEIGHTS["high_velocity"]

            reasons.append(
                "Unusually high transaction velocity"
            )

        # Keep score within 0-100

        score = min(score, 100)

        # Assign risk level

        if score >= 60:

            risk_level = "HIGH"

        elif score >= 30:

            risk_level = "MEDIUM"

        else:

            risk_level = "LOW"

        return {
            "transaction_id": transaction["transaction_id"],
            "customer_id": transaction.get("customer_id"),
            "amount": amount,
            "risk_score": score,
            "risk_level": risk_level,
            "risk_reasons": reasons
        }

    # ---------------------------------------
    # 4. SCORE ALL TRANSACTIONS
    # ---------------------------------------

    def score_all_transactions(self):

        transactions = self.fetch_transaction_signals()

        risk_results = []

        for transaction in transactions:

            result = self.calculate_risk_score(
                transaction
            )

            risk_results.append(result)

        print("\nRisk scoring completed.")

        return risk_results

    # ---------------------------------------
    # 5. UPDATE RISK SCORES IN NEO4J
    # ---------------------------------------

    def update_neo4j(self, risk_results):

        query = """
        UNWIND $rows AS row

        MATCH (t:Transaction {
            transaction_id: row.transaction_id
        })

        SET
            t.risk_score = row.risk_score,
            t.risk_level = row.risk_level,
            t.risk_reasons = row.risk_reasons

        RETURN count(t) AS updated_count
        """

        with self.driver.session() as session:

            result = session.run(
                query,
                rows=risk_results
            )

            updated_count = result.single()["updated_count"]

        print(
            "Neo4j transactions updated:",
            updated_count
        )

        return updated_count

    # ---------------------------------------
    # 6. EXPORT RESULTS TO CSV
    # ---------------------------------------

    def export_results(self, risk_results):

        output_file = (
            self.output_dir / "risk_scores.csv"
        )

        fieldnames = [
            "transaction_id",
            "customer_id",
            "amount",
            "risk_score",
            "risk_level",
            "risk_reasons"
        ]

        with open(
            output_file,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()

            for result in risk_results:

                row = result.copy()

                row["risk_reasons"] = ", ".join(
                    row["risk_reasons"]
                )

                writer.writerow(row)

        print(
            "\nRisk report exported:",
            output_file
        )

    # ---------------------------------------
    # 7. DISPLAY RISK SUMMARY
    # ---------------------------------------

    def display_summary(self, risk_results):

        total = len(risk_results)

        high = sum(
            1 for r in risk_results
            if r["risk_level"] == "HIGH"
        )

        medium = sum(
            1 for r in risk_results
            if r["risk_level"] == "MEDIUM"
        )

        low = sum(
            1 for r in risk_results
            if r["risk_level"] == "LOW"
        )

        print("\n" + "=" * 50)
        print("TRANSACTION RISK SUMMARY")
        print("=" * 50)

        print("Total Transactions:", total)
        print("High Risk:", high)
        print("Medium Risk:", medium)
        print("Low Risk:", low)

        print("\nTOP 10 HIGH RISK TRANSACTIONS")

        high_risk = sorted(
            [
                r for r in risk_results
                if r["risk_level"] == "HIGH"
            ],
            key=lambda x: x["risk_score"],
            reverse=True
        )

        for item in high_risk[:10]:

            print(
                item["transaction_id"],
                "| Score:", item["risk_score"],
                "| Amount:", item["amount"],
                "| Reasons:", ", ".join(item["risk_reasons"])
            )

        print("=" * 50)

    # ---------------------------------------
    # 8. RUN COMPLETE RISK ENGINE
    # ---------------------------------------

    def run(self):

        try:

            risk_results = self.score_all_transactions()

            self.update_neo4j(risk_results)

            self.export_results(risk_results)

            self.display_summary(risk_results)

            return risk_results

        finally:

            self.db.close()


# ---------------------------------------
# MAIN EXECUTION
# ---------------------------------------

if __name__ == "__main__":

    engine = RiskScoringEngine()

    engine.run()
