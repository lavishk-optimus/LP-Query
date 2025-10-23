from datetime import datetime
import azure.functions as func
import logging
import os
from azure.cosmos import CosmosClient
from azure.communication.email import EmailClient

app = func.FunctionApp()

@app.cosmos_db_trigger(
    arg_name="azcosmosdb",
    container_name="funds",
    database_name="lpquery",
    connection="cdblpqueryccprod01_DOCUMENTDB",
    lease_container_name="leases",
    create_lease_container_if_not_exists=True
)
def LPQueryTrigger(azcosmosdb: func.DocumentList):
    logging.info('🔔 CosmosDB Trigger Fired - Checking for NAV/IRR changes...')

    if not azcosmosdb:
        logging.info("No documents changed.")
        return

    cosmos_conn = os.getenv("cdblpqueryccprod01_DOCUMENTDB")
    cosmos_client = CosmosClient.from_connection_string(cosmos_conn)
    database = cosmos_client.get_database_client("lpquery")
    funds_container = database.get_container_client("funds")
    prefs_container = database.get_container_client("alert_preferences")

    # Initialize Azure Communication Services email client
    acs_conn = os.getenv("ACS_CONNECTION_STRING")
    email_client = EmailClient.from_connection_string(acs_conn)

    for doc in azcosmosdb:
        try:
            user_id = doc.get("user_id")
            fund_name = doc.get("fund_name")
            current_nav = float(doc.get("nav", 0))
            current_irr = float(doc.get("net_irr", 0))
            current_date = doc.get("last_reported")

            # Fetch previous record (same user + fund, latest before current date)
            query = f"""
            SELECT TOP 1 c.nav, c.net_irr, c.last_reported
            FROM c
            WHERE c.user_id = '{user_id}'
            AND c.fund_name = '{fund_name}'
            AND c.last_reported < '{current_date}'
            ORDER BY c.last_reported DESC
            """
            items = list(funds_container.query_items(query=query, enable_cross_partition_query=True))
            if not items:
                logging.info(f"No previous record found for {fund_name}, skipping comparison.")
                continue

            prev = items[0]
            prev_nav = float(prev.get("nav", 0))
            prev_irr = float(prev.get("net_irr", 0))

            nav_change = ((current_nav - prev_nav) / prev_nav) * 100 if prev_nav else 0
            irr_change = ((current_irr - prev_irr) / prev_irr) * 100 if prev_irr else 0

            logging.info(f"Fund: {fund_name} | NAV Δ: {nav_change:.2f}% | IRR Δ: {irr_change:.2f}%")

            # Fetch user alert preferences dynamically
            pref_query = f"SELECT * FROM c WHERE c.user_id = '{user_id}'"
            prefs = list(prefs_container.query_items(query=pref_query, enable_cross_partition_query=True))

            if not prefs:
                logging.info(f"No alert preferences found for user: {user_id}")
                continue

            for pref in prefs:
                alert_type = pref.get("alert_type", "NAV")
                threshold_type = pref.get("threshold_type", "Above")
                threshold_value = float(pref.get("threshold_value", 5))
                funds_to_monitor = pref.get("funds", [])
                frequency = pref.get("frequency", "immediate")
                user_email = pref.get("user_email")

                if not user_email:
                    logging.warning(f"No email found for user {user_id}, skipping alert for {fund_name}")
                    continue

                # Skip if fund not in user's preference list
                if fund_name not in funds_to_monitor:
                    continue

                # Pick which change to monitor
                change = nav_change if alert_type.upper() == "NAV" else irr_change
                alerts_container = database.get_container_client("alerts_pending")
                
                # Check threshold condition
                if ((threshold_type == "Above" and change >= threshold_value) or
                    (threshold_type == "Below" and change <= -threshold_value)):

                    if frequency.lower() == "immediate":
                        send_email_alert(email_client, user_email, fund_name, nav_change, irr_change)
                        logging.info(f"🚨 Immediate alert sent for {fund_name} to {user_email}")
                    elif frequency.lower() in ["daily", "weekly"]:
                        store_pending_alert(alerts_container, user_id, fund_name, nav_change, irr_change, frequency)
                        logging.info(f"🗓 Alert for {fund_name} stored for {frequency} dispatch")
                    else:
                        logging.info(f"⏳ Alert for {fund_name} skipped (frequency={frequency})")
                else:
                    logging.info(f"No threshold breach for {fund_name}")

        except Exception as e:
            logging.error(f"Error processing {doc.get('fund_name')}: {e}")


# Email alert
def send_email_alert(email_client, user_email: str, fund_name: str, nav_change: float, irr_change: float):
    subject = f"⚠ NAV/IRR Alert for {fund_name}"
    body = f"""
    Hello,<br><br>
    NAV or IRR for <b>{fund_name}</b> changed significantly.<br><br>
    NAV Change: {nav_change:.2f}%<br>
    IRR Change: {irr_change:.2f}%<br><br>
    Regards,<br>LP Query Team
    """

    message = {
        "senderAddress": "DoNotReply@cf856137-20fd-47dc-b563-302f54e40d38.azurecomm.net",
        "recipients": {"to": [{"address": user_email}]},
        "content": {"subject": subject, "html": body},
    }

    poller = email_client.begin_send(message)
    result = poller.result()
    logging.info(f"📧 Email sent to {user_email} for {fund_name}")


def store_pending_alert(alerts_container, user_id, fund_name, nav_change, irr_change, frequency):
    alert_doc = {
        "id": f"{user_id}_{fund_name}_{frequency}",
        "user_id": user_id,
        "fund_name": fund_name,
        "nav_change": nav_change,
        "irr_change": irr_change,
        "frequency": frequency,
        "timestamp": datetime.utcnow().isoformat()
    }
    alerts_container.upsert_item(alert_doc)
    logging.info(f"🗂 Stored pending alert for {user_id} ({fund_name}) [{frequency}]")


@app.timer_trigger(schedule="0 0 8 * * *", arg_name="mytimer", run_on_startup=False, use_monitor=True)
def DailyAlertBatcher(mytimer: func.TimerRequest):
    """
    Runs every day at 8 AM UTC to send daily or weekly alerts.
    """
    logging.info("⏰ Running Daily/Weekly Alert Batch Job...")

    cosmos_conn = os.getenv("cdblpqueryccprod01_DOCUMENTDB")
    cosmos_client = CosmosClient.from_connection_string(cosmos_conn)
    database = cosmos_client.get_database_client("lpquery")
    alerts_container = database.get_container_client("alerts_pending")
    prefs_container = database.get_container_client("alert_preferences")

    acs_conn = os.getenv("ACS_CONNECTION_STRING")
    email_client = EmailClient.from_connection_string(acs_conn)

    # Fetch all pending alerts
    alerts = list(alerts_container.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))
    if not alerts:
        logging.info("No pending alerts to send.")
        return

    grouped_alerts = {}

    # Group alerts by user and frequency
    for alert in alerts:
        user_id = alert["user_id"]
        frequency = alert.get("frequency", "daily")
        key = f"{user_id}_{frequency}"
        grouped_alerts.setdefault(key, []).append(alert)

    for key, user_alerts in grouped_alerts.items():
        user_id, frequency = key.split("_", 1)

        # Skip weekly alerts unless it's Sunday
        if frequency == "weekly" and datetime.utcnow().weekday() != 6:
            continue

        # Fetch user email dynamically from alert_preferences
        pref_query = f"SELECT TOP 1 c.user_email FROM c WHERE c.user_id = '{user_id}'"
        prefs = list(prefs_container.query_items(query=pref_query, enable_cross_partition_query=True))
        if prefs:
            user_email = prefs[0].get("user_email")
        else:
            logging.warning(f"No email found for {user_id}, skipping summary.")
            continue

        # Build email content
        alert_lines = []
        for a in user_alerts:
            alert_lines.append(
                f"<li><b>{a['fund_name']}</b>: NAV Δ {a['nav_change']:.2f}% | IRR Δ {a['irr_change']:.2f}%</li>"
            )

        if alert_lines:
            body = f"""
            <p>Hello {user_id},</p>
            <p>Here are your {frequency.title()} NAV/IRR alerts:</p>
            <ul>{''.join(alert_lines)}</ul>
            <p>Regards,<br>LP Query Team</p>
            """

            message = {
                "senderAddress": "DoNotReply@cf856137-20fd-47dc-b563-302f54e40d38.azurecomm.net",
                "recipients": {"to": [{"address": user_email}]},
                "content": {"subject": f"{frequency.title()} NAV/IRR Summary", "html": body},
            }

            try:
                poller = email_client.begin_send(message)
                result = poller.result()
                logging.info(f"📧 Sent {frequency} summary to {user_email}")
            except Exception as e:
                logging.error(f"Failed to send {frequency} alert to {user_email}: {e}")

        # Delete processed alerts
        for a in user_alerts:
            alerts_container.delete_item(a["id"], partition_key=a["user_id"])
