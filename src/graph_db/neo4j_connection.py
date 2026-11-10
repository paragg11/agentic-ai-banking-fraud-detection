
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


# Load .env from the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Neo4jConnection:

    def __init__(self):

        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")

        if not all([self.uri, self.username, self.password]):
            raise ValueError(
                "Missing Neo4j configuration. Check your .env file."
            )

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password)
        )

    def verify_connection(self):

        try:
            self.driver.verify_connectivity()

            with self.driver.session(
                database=self.database
            ) as session:

                result = session.run(
                    "RETURN 'Neo4j Connected Successfully!' AS message"
                )

                record = result.single()

                print(record["message"])
                print(f"Database: {self.database}")

                return True

        except Exception as error:

            print(f"Neo4j connection failed: {error}")

            return False

    def close(self):

        if hasattr(self, "driver"):
            self.driver.close()
            print("Neo4j connection closed.")


# Run connection test
if __name__ == "__main__":

    print("BANKING FRAUD DETECTION AGENT")
    print("Testing Neo4j database connection...\n")

    db = Neo4jConnection()

    try:
        db.verify_connection()

    finally:
        db.close()
