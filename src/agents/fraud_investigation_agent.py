
import os
import json
from typing import TypedDict

from dotenv import load_dotenv
from neo4j import GraphDatabase
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama


# ============================================================
# 1. ENVIRONMENT CONFIGURATION
# ============================================================

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


# ============================================================
# 2. INVESTIGATION STATE
# ============================================================

class InvestigationState(TypedDict, total=False):
    transaction_id: str
    transaction: dict
    customer: dict
    merchant: dict
    device: dict
    ip_address: dict
    shared_device: dict
    shared_ip: dict
    customer_history: list
    findings: list
    report: str
    error: str
    risk_score: float
    risk_level: str
    amount: float


# ============================================================
# 3. FRAUD INVESTIGATION AGENT
# ============================================================

class FraudInvestigationAgent:

    def __init__(self):

        if not all([
            NEO4J_URI,
            NEO4J_USERNAME,
            NEO4J_PASSWORD
        ]):
            raise ValueError(
                "Missing Neo4j environment variables."
            )

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

        self.driver.verify_connectivity()

        self.llm = ChatOllama(
            model="mistral:latest",
            temperature=0
        )

        print("Fraud Investigation Agent initialized.")

        self.workflow = self.build_workflow()

    # ========================================================
    # 4. DATABASE HELPER
    # ========================================================

    def execute_query(self, query, parameters=None):

        with self.driver.session(
            database=NEO4J_DATABASE
        ) as session:

            result = session.run(
                query,
                parameters or {}
            )

            return [record.data() for record in result]

    # ========================================================
    # 5. FETCH TRANSACTION DETAILS
    # ========================================================

    def fetch_transaction(self, state):

        transaction_id = state["transaction_id"]

        query = """
        MATCH (t:Transaction {
            transaction_id: $transaction_id
        })

        OPTIONAL MATCH (c:Customer)-[:INITIATED]->(t)
        OPTIONAL MATCH (t)-[:PAID_TO]->(m:Merchant)
        OPTIONAL MATCH (t)-[:USED_DEVICE]->(d:Device)
        OPTIONAL MATCH (t)-[:ORIGINATED_FROM]->(ip:IPAddress)

        RETURN
            properties(t) AS transaction,
            properties(c) AS customer,
            properties(m) AS merchant,
            properties(d) AS device,
            properties(ip) AS ip_address

        LIMIT 1
        """

        records = self.execute_query(
            query,
            {"transaction_id": transaction_id}
        )

        if not records:
            raise ValueError(
                f"Transaction {transaction_id} not found."
            )

        print("Transaction details fetched.")

        return {
            **state,
            **records[0]
        }

    # ========================================================
    # 6. INVESTIGATE SHARED DEVICES
    # ========================================================

    def investigate_shared_device(self, state):

        query = """
        MATCH (t:Transaction {
            transaction_id: $transaction_id
        })-[:USED_DEVICE]->(d:Device)

        MATCH (other:Transaction)-[:USED_DEVICE]->(d)

        OPTIONAL MATCH (c:Customer)-[:INITIATED]->(other)

        WHERE other.transaction_id <> t.transaction_id

        RETURN
            properties(d) AS device,
            count(DISTINCT other.transaction_id)
                AS related_transactions,
            count(DISTINCT c.customer_id)
                AS related_customers,
            collect(DISTINCT c.customer_id)
                AS customer_ids
        """

        records = self.execute_query(
            query,
            {"transaction_id": state["transaction_id"]}
        )

        result = records[0] if records else {}

        print("Shared device investigation completed.")

        return {
            **state,
            "shared_device": result
        }

    # ========================================================
    # 7. INVESTIGATE SHARED IP ADDRESSES
    # ========================================================

    def investigate_shared_ip(self, state):

        query = """
        MATCH (t:Transaction {
            transaction_id: $transaction_id
        })-[:ORIGINATED_FROM]->(ip:IPAddress)

        MATCH (other:Transaction)-[:ORIGINATED_FROM]->(ip)

        OPTIONAL MATCH (c:Customer)-[:INITIATED]->(other)

        WHERE other.transaction_id <> t.transaction_id

        RETURN
            properties(ip) AS ip_address,
            count(DISTINCT other.transaction_id)
                AS related_transactions,
            count(DISTINCT c.customer_id)
                AS related_customers,
            collect(DISTINCT c.customer_id)
                AS customer_ids
        """

        records = self.execute_query(
            query,
            {"transaction_id": state["transaction_id"]}
        )

        result = records[0] if records else {}

        print("Shared IP investigation completed.")

        return {
            **state,
            "shared_ip": result
        }

    # ========================================================
    # 8. FETCH CUSTOMER TRANSACTION HISTORY
    # ========================================================

    def fetch_customer_history(self, state):

        customer = state.get("customer") or {}

        customer_id = customer.get("customer_id")

        if not customer_id:

            return {
                **state,
                "customer_history": []
            }

        query = """
        MATCH (c:Customer {
            customer_id: $customer_id
        })-[:INITIATED]->(t:Transaction)

        RETURN properties(t) AS transaction

        ORDER BY toString(t.timestamp) DESC

        LIMIT 10
        """

        records = self.execute_query(
            query,
            {"customer_id": customer_id}
        )

        history = [
            record["transaction"]
            for record in records
        ]

        print("Customer transaction history fetched.")

        return {
            **state,
            "customer_history": history
        }

    # ========================================================
    # 9. ANALYZE FRAUD EVIDENCE
    # ========================================================

    def analyze_evidence(self, state):

        transaction = state.get("transaction") or {}

        shared_device = state.get("shared_device") or {}

        shared_ip = state.get("shared_ip") or {}

        findings = []

        amount = float(transaction.get("amount") or 0)

        risk_score = float(
            transaction.get("risk_score") or 0
        )

        risk_level = str(
            transaction.get("risk_level") or "UNKNOWN"
        ).upper()

        related_device_customers = int(
            shared_device.get("related_customers") or 0
        )

        related_ip_customers = int(
            shared_ip.get("related_customers") or 0
        )

        # High-value transaction

        if amount >= 50000:

            findings.append(
                "High-value transaction detected."
            )

        # Shared device detection

        if related_device_customers > 0:

            findings.append(
                f"Device is associated with "
                f"{related_device_customers} other customers."
            )

        # Shared IP detection

        if related_ip_customers > 0:

            findings.append(
                f"IP address is associated with "
                f"{related_ip_customers} other customers."
            )

        # Risk score analysis

        if risk_score >= 60:

            findings.append(
                "High risk score detected."
            )

        elif risk_score >= 30:

            findings.append(
                "Medium risk score detected."
            )

        # Customer transaction history

        history = state.get("customer_history", [])

        if len(history) > 0:

            findings.append(
                f"Customer has {len(history)} recent "
                "transactions available for review."
            )

        if not findings:

            findings.append(
                "No suspicious indicators found "
                "in the available investigation data."
            )

        print("Fraud evidence analysis completed.")

        return {
            **state,
            "findings": findings,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "amount": amount
        }

    # ========================================================
    # 10. GENERATE INVESTIGATION REPORT
    # ========================================================

    def generate_report(self, state):

        transaction = state.get("transaction") or {}

        customer = state.get("customer") or {}

        merchant = state.get("merchant") or {}

        device = state.get("device") or {}

        ip_address = state.get("ip_address") or {}

        shared_device = state.get("shared_device") or {}

        shared_ip = state.get("shared_ip") or {}

        customer_history = state.get("customer_history", [])

        findings = state.get("findings", [])

        risk_score = state.get("risk_score", 0)

        risk_level = state.get("risk_level", "UNKNOWN")

        # ----------------------------------------------------
        # DETERMINISTIC INVESTIGATION REPORT
        # ----------------------------------------------------

        report = f"""
==================================================
          FRAUD INVESTIGATION REPORT
==================================================

TRANSACTION DETAILS

Transaction ID : {transaction.get('transaction_id')}
Customer ID    : {customer.get('customer_id')}
Merchant ID    : {merchant.get('merchant_id')}
Amount         : {transaction.get('amount')}
Timestamp      : {transaction.get('timestamp')}

--------------------------------------------------

DEVICE DETAILS

Device ID      : {device.get('device_id')}
Device Type    : {device.get('device_type')}

IP DETAILS

IP Address     : {ip_address.get('ip_address')}

--------------------------------------------------

SHARED DEVICE ANALYSIS

Related Transactions : {shared_device.get('related_transactions', 0)}
Related Customers    : {shared_device.get('related_customers', 0)}

SHARED IP ANALYSIS

Related Transactions : {shared_ip.get('related_transactions', 0)}
Related Customers    : {shared_ip.get('related_customers', 0)}

--------------------------------------------------

CUSTOMER HISTORY

Recent Transactions : {len(customer_history)}

--------------------------------------------------

RISK ASSESSMENT

Risk Score     : {risk_score}
Risk Level     : {risk_level}

--------------------------------------------------

INVESTIGATION FINDINGS

"""

        for index, finding in enumerate(findings, 1):

            report += f"{index}. {finding}\n"

        report += """
--------------------------------------------------

INVESTIGATION SUMMARY

"""

        if risk_level == "HIGH":

            report += (
                "\nHIGH PRIORITY: Manual fraud investigation "
                "and review are recommended."
            )

        elif risk_level == "MEDIUM":

            report += (
                "\nMEDIUM PRIORITY: Additional transaction "
                "verification is recommended."
            )

        else:

            report += (
                "\nLOWER PRIORITY: No high-risk indicators "
                "were identified by the current checks."
            )

        report += """

==================================================
             END OF INVESTIGATION
==================================================
"""

        # ----------------------------------------------------
        # AI-POWERED INVESTIGATION ANALYSIS USING MISTRAL
        # ----------------------------------------------------

        try:

            prompt = f"""
You are a banking fraud investigation assistant.

Analyze the following transaction investigation data.

TRANSACTION:
{json.dumps(transaction, indent=2, default=str)}

CUSTOMER:
{json.dumps(customer, indent=2, default=str)}

MERCHANT:
{json.dumps(merchant, indent=2, default=str)}

DEVICE:
{json.dumps(device, indent=2, default=str)}

IP ADDRESS:
{json.dumps(ip_address, indent=2, default=str)}

SHARED DEVICE:
{json.dumps(shared_device, indent=2, default=str)}

SHARED IP:
{json.dumps(shared_ip, indent=2, default=str)}

CUSTOMER HISTORY:
{json.dumps(customer_history, indent=2, default=str)}

INVESTIGATION FINDINGS:
{json.dumps(findings, indent=2, default=str)}

DETERMINISTIC RISK SCORE: {risk_score}

DETERMINISTIC RISK LEVEL: {risk_level}

Instructions:

1. Explain the investigation findings.
2. Identify suspicious indicators supported by the data.
3. Explain why the assigned risk level is appropriate.
4. Recommend practical investigation actions.
5. Do not invent missing information.
6. Do not modify the risk score or risk level.
7. Do not claim fraud is confirmed without sufficient evidence.
8. Distinguish between suspicious patterns and confirmed fraud.

Write a concise professional investigation analysis.
"""

            response = self.llm.invoke(prompt)

            ai_analysis = response.content.strip()

            if ai_analysis:

                report = report.replace(
                    "END OF INVESTIGATION",
                    "AI INVESTIGATION ANALYSIS\n\n"
                    + ai_analysis
                    + "\n\nEND OF INVESTIGATION"
                )

        except Exception as e:

            print(f"Mistral analysis unavailable: {e}")

            print(
                "Using deterministic investigation report."
            )

        print(report)

        return {
            **state,
            "report": report
        }

    # ========================================================
    # 11. BUILD LANGGRAPH WORKFLOW
    # ========================================================

    def build_workflow(self):

        workflow = StateGraph(InvestigationState)

        workflow.add_node(
            "fetch_transaction",
            self.fetch_transaction
        )

        workflow.add_node(
            "investigate_device",
            self.investigate_shared_device
        )

        workflow.add_node(
            "investigate_ip",
            self.investigate_shared_ip
        )

        workflow.add_node(
            "customer_history",
            self.fetch_customer_history
        )

        workflow.add_node(
            "analyze_evidence",
            self.analyze_evidence
        )

        workflow.add_node(
            "generate_report",
            self.generate_report
        )

        # Entry point

        workflow.set_entry_point("fetch_transaction")

        # Sequential investigation pipeline

        workflow.add_edge(
            "fetch_transaction",
            "investigate_device"
        )

        workflow.add_edge(
            "investigate_device",
            "investigate_ip"
        )

        workflow.add_edge(
            "investigate_ip",
            "customer_history"
        )

        workflow.add_edge(
            "customer_history",
            "analyze_evidence"
        )

        workflow.add_edge(
            "analyze_evidence",
            "generate_report"
        )

        workflow.add_edge(
            "generate_report",
            END
        )

        return workflow.compile()

    # ========================================================
    # 12. RUN INVESTIGATION
    # ========================================================

    def run_investigation(self, transaction_id):

        print("\nStarting Fraud Investigation...")

        try:

            initial_state = {
                "transaction_id": transaction_id
            }

            result = self.workflow.invoke(initial_state)

            return result

        except Exception as error:

            print("Investigation failed:", error)

            return {
                "error": str(error)
            }

    # ========================================================
    # 13. CLOSE DATABASE CONNECTION
    # ========================================================

    def close(self):

        self.driver.close()

        print("Neo4j connection closed.")


# ============================================================
# 14. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    agent = FraudInvestigationAgent()

    try:

        transaction_id = input(
            "Enter Transaction ID: "
        ).strip()

        if not transaction_id:

            raise ValueError(
                "Transaction ID cannot be empty."
            )

        result = agent.run_investigation(
            transaction_id
        )

        if "report" in result:

            os.makedirs(
                "data/processed",
                exist_ok=True
            )

            report_path = (
                "data/processed/"
                f"investigation_{transaction_id}.txt"
            )

            with open(
                report_path,
                "w",
                encoding="utf-8"
            ) as file:

                file.write(result["report"])

            print(
                f"\nReport saved to: {report_path}"
            )

        else:

            print(
                "\nInvestigation could not be completed."
            )

    finally:

        agent.close()
