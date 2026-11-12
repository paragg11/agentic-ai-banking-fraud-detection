import os
import json
import re
from io import BytesIO
from datetime import datetime

import requests
import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Banking Fraud Detection",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "240"))


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "investigation_history": [],
    "last_result": None,
    "last_error": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# DATA HELPERS
# ============================================================

def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def first_value(data, *keys, default="Unknown"):
    data = safe_dict(data)
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return default


def nested_value(data, parent, *keys, default="Unknown"):
    return first_value(safe_dict(data).get(parent), *keys, default=default)


def money(value):
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "Not available"


def number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_response(response_json):
    """
    Supports the FastAPI response format used by this project:
    {"investigation": {...}}.
    Also tolerates a direct investigation dictionary.
    """
    payload = safe_dict(response_json)
    investigation = payload.get("investigation")

    if isinstance(investigation, dict):
        return investigation

    # Some API versions may wrap the result one level deeper.
    if isinstance(payload.get("result"), dict):
        result = payload["result"]
        if isinstance(result.get("investigation"), dict):
            return result["investigation"]
        return result

    return payload


def get_transaction(data):
    return safe_dict(data.get("transaction"))


def get_customer(data):
    return safe_dict(data.get("customer"))


def get_merchant(data):
    return safe_dict(data.get("merchant"))


def get_device(data):
    return safe_dict(data.get("device"))


def get_ip(data):
    return safe_dict(data.get("ip_address"))


def get_shared_device(data):
    return safe_dict(data.get("shared_device"))


def get_shared_ip(data):
    return safe_dict(data.get("shared_ip"))


def get_device_id(data):
    shared = get_shared_device(data)
    # Actual backend structure: shared_device.device.device_id
    nested = safe_dict(shared.get("device"))
    return first_value(nested, "device_id", default=first_value(get_device(data), "device_id"))


def get_ip_address(data):
    shared = get_shared_ip(data)
    # Actual backend structure: shared_ip.ip_address.ip_address
    nested = safe_dict(shared.get("ip_address"))
    return first_value(nested, "ip_address", default=first_value(get_ip(data), "ip_address"))


def extract_ai_analysis(report):
    """Extract the LLM section from the generated text report."""
    if not isinstance(report, str) or not report.strip():
        return ""

    markers = [
        "AI INVESTIGATION ANALYSIS",
        "AI INVESTIGATION ANALYSIS:",
    ]

    for marker in markers:
        if marker in report:
            section = report.split(marker, 1)[1]
            section = re.split(
                r"\n\s*END OF INVESTIGATION",
                section,
                maxsplit=1,
            )[0]
            return section.strip()

    return ""


def extract_investigation(response_json):
    data = normalize_response(response_json)

    if data.get("error"):
        raise RuntimeError(str(data["error"]))

    if not get_transaction(data):
        raise ValueError(
            "The API response did not contain transaction details. "
            "Open 'Complete API JSON' to inspect the returned structure."
        )

    return data


# ============================================================
# REPORT GENERATION
# ============================================================

def build_report_text(data):
    transaction = get_transaction(data)
    customer = get_customer(data)
    merchant = get_merchant(data)
    device_id = get_device_id(data)
    ip_address = get_ip_address(data)
    shared_device = get_shared_device(data)
    shared_ip = get_shared_ip(data)

    report = data.get("report")
    if isinstance(report, str) and report.strip():
        return report

    lines = [
        "=" * 58,
        "             FRAUD INVESTIGATION REPORT",
        "=" * 58,
        "",
        "TRANSACTION DETAILS",
        f"Transaction ID : {first_value(transaction, 'transaction_id', default=data.get('transaction_id'))}",
        f"Customer ID    : {first_value(customer, 'customer_id')}",
        f"Merchant ID    : {first_value(merchant, 'merchant_id')}",
        f"Amount         : {money(transaction.get('amount'))}",
        f"Timestamp      : {first_value(transaction, 'timestamp')}",
        f"Channel        : {first_value(transaction, 'channel')}",
        f"Status         : {first_value(transaction, 'status')}",
        "",
        "DEVICE AND IP DETAILS",
        f"Device ID      : {device_id}",
        f"IP Address     : {ip_address}",
        "",
        "SHARED RESOURCE ANALYSIS",
        f"Device-related transactions : {shared_device.get('related_transactions', 0)}",
        f"Device-related customers    : {shared_device.get('related_customers', 0)}",
        f"IP-related transactions     : {shared_ip.get('related_transactions', 0)}",
        f"IP-related customers        : {shared_ip.get('related_customers', 0)}",
        "",
        "RISK ASSESSMENT",
        f"Risk Score : {data.get('risk_score', transaction.get('risk_score', 'Unknown'))}",
        f"Risk Level : {data.get('risk_level', transaction.get('risk_level', 'Unknown'))}",
        "",
        "INVESTIGATION FINDINGS",
    ]

    findings = safe_list(data.get("findings"))
    for index, finding in enumerate(findings, 1):
        lines.append(f"{index}. {finding}")

    lines += ["", "=" * 58]
    return "\n".join(lines)


def create_pdf_report(data):
    """Create a PDF using ReportLab's Platypus flowables."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Preformatted,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PDF export requires ReportLab. Install it with: pip install reportlab"
        ) from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Fraud Investigation Report",
        author="AI Banking Fraud Detection System",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#17365D"),
        spaceBefore=10,
        spaceAfter=5,
    )
    body_style = styles["BodyText"]

    transaction = get_transaction(data)
    customer = get_customer(data)
    merchant = get_merchant(data)
    shared_device = get_shared_device(data)
    shared_ip = get_shared_ip(data)

    story = [
        Paragraph("AI BANKING FRAUD DETECTION", title_style),
        Paragraph("Transaction Investigation Report", styles["Heading2"]),
        Spacer(1, 8),
    ]

    rows = [
        ["Field", "Value"],
        ["Transaction ID", str(first_value(transaction, "transaction_id", default=data.get("transaction_id")))],
        ["Customer ID", str(first_value(customer, "customer_id"))],
        ["Merchant ID", str(first_value(merchant, "merchant_id"))],
        ["Amount", money(transaction.get("amount"))],
        ["Timestamp", str(first_value(transaction, "timestamp"))],
        ["Channel", str(first_value(transaction, "channel"))],
        ["Transaction Type", str(first_value(transaction, "transaction_type"))],
        ["Status", str(first_value(transaction, "status"))],
        ["Risk Score", str(data.get("risk_score", transaction.get("risk_score", "Unknown")))],
        ["Risk Level", str(data.get("risk_level", transaction.get("risk_level", "Unknown")))],
        ["Shared Device Customers", str(shared_device.get("related_customers", 0))],
        ["Shared IP Customers", str(shared_ip.get("related_customers", 0))],
    ]

    table = Table(rows, colWidths=[58 * mm, 112 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#EEF3F8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([table, Spacer(1, 12)])

    story.append(Paragraph("Investigation Findings", section_style))
    findings = safe_list(data.get("findings"))
    if findings:
        for index, finding in enumerate(findings, 1):
            story.append(Paragraph(f"{index}. {str(finding)}", body_style))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No findings were supplied by the API.", body_style))

    report = data.get("report", "")
    ai_analysis = extract_ai_analysis(report)
    if ai_analysis:
        story.append(Paragraph("AI Investigation Analysis", section_style))
        story.append(Preformatted(ai_analysis, styles["Code"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Note: A risk indicator is not proof of fraud. Final decisions require "
        "appropriate human review and supporting evidence.",
        styles["Italic"],
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# VISUALIZATION HELPERS
# ============================================================

def dot_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
    )



def create_fraud_graph(data):
    """
    Create a fraud relationship graph using investigation API data.
    Displays customer, transaction, merchant, device, IP
    and related customers.
    """

    transaction = get_transaction(data)
    customer = get_customer(data)
    merchant = get_merchant(data)
    shared_device = get_shared_device(data)
    shared_ip = get_shared_ip(data)

    transaction_id = first_value(
        transaction,
        "transaction_id",
        default=data.get("transaction_id", "Transaction")
    )

    customer_id = first_value(customer, "customer_id")
    merchant_id = first_value(merchant, "merchant_id")
    device_id = get_device_id(data)
    ip_address = get_ip_address(data)

    nodes = []
    edges = []

    def node(node_id, label, color, shape="box"):
        nodes.append(
            f'"{dot_escape(node_id)}" '
            f'[label="{dot_escape(label)}", '
            f'fillcolor="{color}", '
            f'color="#64748B", '
            f'style="filled", '
            f'shape="{shape}"];'
        )

    def edge(source, target, label):
        edges.append(
            f'"{dot_escape(source)}" -> "{dot_escape(target)}" '
            f'[label="{dot_escape(label)}", color="#64748B"];'
        )

    # Main customer and transaction
    node("customer", f"Customer\n{customer_id}", "#DBEAFE", "ellipse")
    node("transaction", f"Transaction\n{transaction_id}", "#FEF3C7")

    edge("customer", "transaction", "initiated")

    # Merchant
    if merchant_id != "Unknown":
        node("merchant", f"Merchant\n{merchant_id}", "#DCFCE7")
        edge("transaction", "merchant", "paid to")

    # Device
    if device_id != "Unknown":
        node("device", f"Device\n{device_id}", "#FCE7F3")
        edge("transaction", "device", "used")

    # IP address
    if ip_address != "Unknown":
        node("ip", f"IP Address\n{ip_address}", "#EDE9FE")
        edge("transaction", "ip", "originated from")

    # Related customers sharing devices
    device_customers = safe_list(
        shared_device.get("customer_ids")
    )[:10]

    if device_customers:
        node(
            "device_cluster",
            "Customers sharing device",
            "#FCE7F3",
            "diamond"
        )

        if device_id != "Unknown":
            edge("device", "device_cluster", "shared by")

        for index, related_customer in enumerate(device_customers):
            related_node = f"device_customer_{index}"

            node(
                related_node,
                f"Customer\n{related_customer}",
                "#F1F5F9",
                "ellipse"
            )

            edge("device_cluster", related_node, "associated")

    # Related customers sharing IP addresses
    ip_customers = safe_list(
        shared_ip.get("customer_ids")
    )[:10]

    if ip_customers:
        node(
            "ip_cluster",
            "Customers sharing IP",
            "#EDE9FE",
            "diamond"
        )

        if ip_address != "Unknown":
            edge("ip", "ip_cluster", "shared by")

        for index, related_customer in enumerate(ip_customers):
            related_node = f"ip_customer_{index}"

            node(
                related_node,
                f"Customer\n{related_customer}",
                "#F1F5F9",
                "ellipse"
            )

            edge("ip_cluster", related_node, "associated")

    # Build valid Graphviz DOT
    dot_graph = (
        "digraph FraudNetwork {\n"
        'graph [bgcolor="transparent", pad="0.25", '
        'nodesep="0.35", ranksep="0.75"];\n'
        'rankdir="LR";\n'
        'node [fontname="Arial", fontsize="10"];\n'
        'edge [fontname="Arial", fontsize="9"];\n'
        + "\n".join(nodes)
        + "\n"
        + "\n".join(edges)
        + "\n}"
    )

    return dot_graph


# ============================================================
# API CALL
# ============================================================

def investigate_transaction(transaction_id):
    url = f"{API_URL}/investigate"
    response = requests.post(
        url,
        json={"transaction_id": transaction_id.strip()},
        timeout=API_TIMEOUT,
    )
    response.raise_for_status()
    return extract_investigation(response.json())


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("🏦 Fraud Intelligence")
    st.caption("AI-Powered Banking Investigation")
    st.divider()

    st.subheader("System Modules")
    st.markdown(
        """
        - Transaction Analysis
        - Shared Device Detection
        - Shared IP Detection
        - Customer History
        - AI Evidence Analysis
        - Investigation Reports
        - Fraud Network Visualization
        """
    )

    st.divider()
    st.subheader("Session Investigations")
    st.metric("Total Investigations", len(st.session_state.investigation_history))

    if st.button("Clear Session History", use_container_width=True):
        st.session_state.investigation_history = []
        st.session_state.last_result = None
        st.rerun()

    st.divider()
    st.caption(f"Backend: {API_URL}")


# ============================================================
# MAIN HEADER AND INVESTIGATION FORM
# ============================================================

st.title("🏦 AI Banking Fraud Detection System")
st.caption("Graph-Based Fraud Detection | LangGraph | Neo4j | Mistral AI")
st.divider()

st.success("Backend investigation interface ready. Enter a transaction ID to begin.")

with st.form("investigation_form"):
    transaction_id_input = st.text_input(
        "Enter Transaction ID",
        value="TXN001502",
        placeholder="Example: TXN001502",
    )
    submitted = st.form_submit_button(
        "🚀 Investigate Transaction",
        type="primary",
        use_container_width=False,
    )

if submitted:
    if not transaction_id_input.strip():
        st.warning("Please enter a valid transaction ID.")
    else:
        try:
            with st.spinner("AI agent is investigating the transaction..."):
                investigation_data = investigate_transaction(transaction_id_input)

            st.session_state.last_result = {
                "transaction_id": transaction_id_input.strip(),
                "data": investigation_data,
                "investigated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            st.session_state.last_error = None

            transaction = get_transaction(investigation_data)
            history_item = {
                "transaction_id": transaction_id_input.strip(),
                "risk_level": investigation_data.get(
                    "risk_level", transaction.get("risk_level", "UNKNOWN")
                ),
                "risk_score": investigation_data.get(
                    "risk_score", transaction.get("risk_score", 0)
                ),
                "investigated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            st.session_state.investigation_history.insert(0, history_item)
            st.session_state.investigation_history = (
                st.session_state.investigation_history[:50]
            )
            st.success("Investigation completed successfully!")

        except requests.exceptions.ConnectionError:
            st.session_state.last_error = (
                f"Could not connect to the backend at {API_URL}. "
                "Start FastAPI first and confirm that it is listening on port 8000."
            )
        except requests.exceptions.Timeout:
            st.session_state.last_error = (
                f"The investigation exceeded the {API_TIMEOUT}-second API timeout."
            )
        except requests.exceptions.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.text
            except Exception:
                pass
            st.session_state.last_error = f"Backend returned an HTTP error: {exc}. {detail}"
        except Exception as exc:
            st.session_state.last_error = f"Investigation failed: {exc}"

if st.session_state.last_error:
    st.error(st.session_state.last_error)


# ============================================================
# DISPLAY INVESTIGATION RESULT
# ============================================================

last_result = st.session_state.last_result

if last_result:
    data = safe_dict(last_result.get("data"))
    transaction = get_transaction(data)
    customer = get_customer(data)
    merchant = get_merchant(data)
    device = get_device(data)
    ip_data = get_ip(data)
    shared_device = get_shared_device(data)
    shared_ip = get_shared_ip(data)
    customer_history = safe_list(data.get("customer_history"))
    findings = safe_list(data.get("findings"))
    report_text = build_report_text(data)

    risk_score = number(
        data.get("risk_score", transaction.get("risk_score", 0))
    )
    risk_level = str(
        data.get("risk_level", transaction.get("risk_level", "UNKNOWN"))
    ).upper()
    amount = transaction.get("amount", data.get("amount", 0))
    risk_reasons = safe_list(transaction.get("risk_reasons"))

    st.divider()

    # KPI dashboard
    st.header("📊 Investigation Dashboard")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Risk Score", f"{risk_score:.1f}/100")
    k2.metric("Risk Level", risk_level)
    k3.metric("Transaction Amount", money(amount))
    k4.metric("Risk Indicators", len(risk_reasons))

    if risk_level == "HIGH":
        st.error("HIGH RISK: Manual fraud investigation and review are recommended.")
    elif risk_level == "MEDIUM":
        st.warning("MEDIUM RISK: Additional transaction verification is recommended.")
    elif risk_level == "LOW":
        st.success("LOW RISK: No high-risk indicators were identified by current checks.")
    else:
        st.info(f"Risk classification returned by backend: {risk_level}")

    st.progress(max(0.0, min(risk_score / 100.0, 1.0)))

    # Transaction details
    st.divider()
    st.header("💳 Transaction Details")
    left, right = st.columns(2)

    with left:
        st.write("**Transaction ID**", first_value(transaction, "transaction_id", default=data.get("transaction_id")))
        st.write("**Customer ID**", first_value(customer, "customer_id"))
        st.write("**Merchant ID**", first_value(merchant, "merchant_id"))
        st.write("**Amount**", money(amount))

    with right:
        st.write("**Channel**", first_value(transaction, "channel"))
        st.write("**Transaction Type**", first_value(transaction, "transaction_type"))
        st.write("**Status**", first_value(transaction, "status"))
        st.write("**Timestamp**", first_value(transaction, "timestamp"))

    # Risk indicators
    st.divider()
    st.header("⚠️ Risk Indicators")
    if risk_reasons:
        for reason in risk_reasons:
            st.warning(str(reason))
    else:
        st.info("No transaction risk reasons were supplied.")

    # Shared device analysis
    st.divider()
    st.header("📱 Shared Device Analysis")
    device_id = get_device_id(data)
    d1, d2, d3 = st.columns(3)
    d1.metric("Device ID", device_id)
    d2.metric("Related Transactions", int(number(shared_device.get("related_transactions", 0))))
    d3.metric("Other Customers", int(number(shared_device.get("related_customers", 0))))

    device_customers = safe_list(shared_device.get("customer_ids"))
    with st.expander(f"View related device customers ({len(device_customers)})", expanded=False):
        if device_customers:
            st.dataframe(
                pd.DataFrame({"Related Customer ID": device_customers}),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No related customer IDs were returned for this device.")

    # Shared IP analysis
    st.divider()
    st.header("🌐 Shared IP Analysis")
    ip_address = get_ip_address(data)
    i1, i2, i3 = st.columns(3)
    i1.metric("IP Address", ip_address)
    i2.metric("Related Transactions", int(number(shared_ip.get("related_transactions", 0))))
    i3.metric("Other Customers", int(number(shared_ip.get("related_customers", 0))))

    ip_customers = safe_list(shared_ip.get("customer_ids"))
    with st.expander(f"View related IP customers ({len(ip_customers)})", expanded=False):
        if ip_customers:
            st.dataframe(
                pd.DataFrame({"Related Customer ID": ip_customers}),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No related customer IDs were returned for this IP address.")

    # Customer transaction history
    st.divider()
    st.header("👤 Customer Transaction History")
    st.caption(
        f"Customer: {first_value(customer, 'customer_id')} | "
        f"Transactions returned: {len(customer_history)}"
    )

    if customer_history:
        history_df = pd.DataFrame(customer_history)

        visible_columns = [
            column for column in [
                "transaction_id",
                "timestamp",
                "amount",
                "channel",
                "transaction_type",
                "status",
                "risk_score",
                "risk_level",
                "pattern_type",
                "is_fraud",
            ]
            if column in history_df.columns
        ]

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            channels = sorted(
                str(value) for value in history_df["channel"].dropna().unique()
            ) if "channel" in history_df.columns else []
            selected_channels = st.multiselect(
                "Filter by channel",
                channels,
                default=channels,
            )
        with filter_col2:
            statuses = sorted(
                str(value) for value in history_df["status"].dropna().unique()
            ) if "status" in history_df.columns else []
            selected_statuses = st.multiselect(
                "Filter by status",
                statuses,
                default=statuses,
            )

        filtered_df = history_df.copy()
        if "channel" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["channel"].astype(str).isin(selected_channels)
            ]
        if "status" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["status"].astype(str).isin(selected_statuses)
            ]

        st.dataframe(
            filtered_df[visible_columns] if visible_columns else filtered_df,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "⬇️ Download Customer History CSV",
            data=filtered_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{first_value(customer, 'customer_id', default='customer')}_history.csv",
            mime="text/csv",
        )
    else:
        st.info("No customer transaction history was returned.")

    # Findings
    st.divider()
    st.header("🔎 Investigation Findings")
    if findings:
        for index, finding in enumerate(findings, 1):
            st.markdown(f"**{index}.** {finding}")
    else:
        st.info("No investigation findings were returned.")

    # AI analysis
    st.divider()
    st.header("🤖 AI Investigation Analysis")
    ai_analysis = extract_ai_analysis(data.get("report", ""))
    if ai_analysis:
        st.markdown(ai_analysis)
    else:
        st.info(
            "No separate AI analysis section was found in the report. "
            "The deterministic findings and report are still available below."
        )

    # Fraud network graph
    st.divider()
    st.header("🕸️ Fraud Network Visualization")
    st.caption(
        "The graph shows relationships returned by the investigation API. "
        "For readability, up to 10 related customers per shared resource are displayed."
    )
    try:
        st.graphviz_chart(create_fraud_graph(data), use_container_width=True)
    except Exception as exc:
        st.warning(
            "The relationship data is available, but Graphviz rendering failed. "
            f"Install the graphviz Python package if needed. Details: {exc}"
        )

    # Reports
    st.divider()
    st.header("📄 Investigation Report")
    st.text_area(
        "Generated Investigation Report",
        value=report_text,
        height=360,
    )

    report_filename = (
        f"fraud_investigation_{first_value(transaction, 'transaction_id', default='report')}.txt"
    )
    st.download_button(
        "⬇️ Download Investigation Report (TXT)",
        data=report_text.encode("utf-8"),
        file_name=report_filename,
        mime="text/plain",
    )

    try:
        pdf_bytes = create_pdf_report(data)
        st.download_button(
            "⬇️ Download Investigation Report (PDF)",
            data=pdf_bytes,
            file_name=f"fraud_investigation_{first_value(transaction, 'transaction_id', default='report')}.pdf",
            mime="application/pdf",
        )
    except RuntimeError as exc:
        st.info(str(exc))

    # Full JSON
    with st.expander("🔧 View Complete Investigation JSON"):
        st.json(data)

else:
    st.info("No investigation result yet. Enter a transaction ID above and click Investigate.")


# ============================================================
# INVESTIGATION HISTORY
# ============================================================

st.divider()
st.header("📚 Investigation History")

if st.session_state.investigation_history:
    history_df = pd.DataFrame(st.session_state.investigation_history)
    st.dataframe(history_df, use_container_width=True, hide_index=True)
else:
    st.info("No investigation history available in this session.")


# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption(
    "AI Banking Fraud Detection System | Powered by LangGraph, Neo4j, "
    "FastAPI, Streamlit and Mistral AI"
)