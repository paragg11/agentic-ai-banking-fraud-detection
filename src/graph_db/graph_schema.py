
from src.graph_db.neo4j_connection import Neo4jConnection


class FraudGraphSchema:

    def __init__(self):
        self.db = Neo4jConnection()

    def create_constraints(self):

        constraints = [
            """
            CREATE CONSTRAINT customer_id_unique IF NOT EXISTS
            FOR (c:Customer)
            REQUIRE c.customer_id IS UNIQUE
            """,

            """
            CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS
            FOR (t:Transaction)
            REQUIRE t.transaction_id IS UNIQUE
            """,

            """
            CREATE CONSTRAINT device_id_unique IF NOT EXISTS
            FOR (d:Device)
            REQUIRE d.device_id IS UNIQUE
            """,

            """
            CREATE CONSTRAINT ip_address_unique IF NOT EXISTS
            FOR (ip:IPAddress)
            REQUIRE ip.ip_address IS UNIQUE
            """,

            """
            CREATE CONSTRAINT merchant_id_unique IF NOT EXISTS
            FOR (m:Merchant)
            REQUIRE m.merchant_id IS UNIQUE
            """
        ]

        with self.db.driver.session(
            database=self.db.database
        ) as session:

            for query in constraints:
                session.run(query).consume()

        print("All graph constraints created successfully!")

    def create_indexes(self):

        indexes = [
            """
            CREATE INDEX transaction_timestamp_idx IF NOT EXISTS
            FOR (t:Transaction)
            ON (t.timestamp)
            """,

            """
            CREATE INDEX transaction_amount_idx IF NOT EXISTS
            FOR (t:Transaction)
            ON (t.amount)
            """
        ]

        with self.db.driver.session(
            database=self.db.database
        ) as session:

            for query in indexes:
                session.run(query).consume()

        print("All graph indexes created successfully!")

    def setup_schema(self):

        try:
            self.create_constraints()
            self.create_indexes()

            print("\nBanking Fraud Knowledge Graph Schema Ready!")

        except Exception as error:
            print(f"Schema setup failed: {error}")

            raise

        finally:
            self.db.close()


if __name__ == "__main__":

    print("BANKING FRAUD DETECTION AGENT")
    print("Initializing Knowledge Graph Schema...\n")

    schema = FraudGraphSchema()
    schema.setup_schema()
