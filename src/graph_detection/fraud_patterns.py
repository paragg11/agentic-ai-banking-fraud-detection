
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


class FraudPatternDetector:

    def __init__(self):

        if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
            raise ValueError("Missing Neo4j environment variables.")

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def detect_shared_devices(self):

        query = """
        MATCH (c:Customer)-[:INITIATED]->(t:Transaction)
              -[:USED_DEVICE]->(d:Device)

        WITH d, collect(DISTINCT c.customer_id) AS customers,
             count(DISTINCT t) AS transaction_count

        WHERE size(customers) >= $min_customers

        RETURN d.device_id AS device_id,
               customers,
               size(customers) AS customer_count,
               transaction_count

        ORDER BY customer_count DESC
        LIMIT 20
        """

        return self.run_query(query, {"min_customers": 2})

    def detect_shared_ips(self):

        query = """
        MATCH (c:Customer)-[:INITIATED]->(t:Transaction)
              -[:ORIGINATED_FROM]->(ip:IPAddress)

        WITH ip, collect(DISTINCT c.customer_id) AS customers,
             count(DISTINCT t) AS transaction_count

        WHERE size(customers) >= $min_customers

        RETURN ip.ip_address AS ip_address,
               customers,
               size(customers) AS customer_count,
               transaction_count

        ORDER BY customer_count DESC
        LIMIT 20
        """

        return self.run_query(query, {"min_customers": 2})

    def detect_flagged_transactions(self):

        query = """
        MATCH (t:Transaction)

        WHERE t.is_fraud = true
           OR toLower(toString(t.is_fraud)) IN ['true', '1', 'yes']

        OPTIONAL MATCH (c:Customer)-[:INITIATED]->(t)
        OPTIONAL MATCH (t)-[:PAID_TO]->(m:Merchant)

        RETURN t.transaction_id AS transaction_id,
               c.customer_id AS customer_id,
               t.amount AS amount,
               m.merchant_id AS merchant_id,
               t.pattern_type AS pattern_type

        ORDER BY t.amount DESC
        LIMIT 50
        """

        return self.run_query(query)

    def detect_high_value_transactions(self, threshold=50000):

        query = """
        MATCH (t:Transaction)

        WHERE toFloat(t.amount) >= $threshold

        OPTIONAL MATCH (c:Customer)-[:INITIATED]->(t)
        OPTIONAL MATCH (t)-[:PAID_TO]->(m:Merchant)

        RETURN t.transaction_id AS transaction_id,
               c.customer_id AS customer_id,
               t.amount AS amount,
               m.merchant_id AS merchant_id

        ORDER BY toFloat(t.amount) DESC
        LIMIT 50
        """

        return self.run_query(query, {"threshold": threshold})

    def run_query(self, query, parameters=None):

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            result = session.run(query, parameters or {})

            return [record.data() for record in result]

    def run_all_detections(self):

        detections = {
            "SHARED DEVICES": self.detect_shared_devices(),
            "SHARED IP ADDRESSES": self.detect_shared_ips(),
            "FLAGGED TRANSACTIONS": self.detect_flagged_transactions(),
            "HIGH VALUE TRANSACTIONS": self.detect_high_value_transactions()
        }

        for name, results in detections.items():

            print("\n" + "=" * 55)
            print(name)
            print("=" * 55)

            print(f"Records detected: {len(results)}")

            for item in results[:5]:
                print(item)

        return detections


if __name__ == "__main__":

    detector = FraudPatternDetector()

    try:
        detector.run_all_detections()

    finally:
        detector.close()
