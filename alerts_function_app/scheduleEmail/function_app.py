import os
import io
import csv
import base64
import datetime
import logging
import azure.functions as func
from azure.functions import FunctionApp
from azure.cosmos import CosmosClient
from azure.communication.email import EmailClient

# Initialize Function App
app = FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.function_name(name="SendScheduledEmails")
@app.schedule(schedule="0 30 5 * * *", arg_name="mytimer", run_on_startup=False, use_monitor=True)
def send_scheduled_emails(mytimer: func.TimerRequest) -> None:
    logging.info("📬 Scheduled email job started")

    # Load environment variables
    COSMOS_CONN = os.getenv("COSMOS_CONN")
    COSMOS_DB = os.getenv("COSMOS_DB")
    COSMOS_SCHEDULE_CONTAINER = os.getenv("COSMOS_SCHEDULE_CONTAINER")
    COSMOS_FUNDS_CONTAINER = os.getenv("COSMOS_FUNDS_CONTAINER")
    ACS_CONN = os.getenv("ACS_CONNECTION_STRING")
    FROM_EMAIL = os.getenv("FROM_EMAIL")

    today = datetime.date.today().isoformat()
    logging.info(f"Processing email schedules for date: {today}")

    # Setup clients
    cosmos_client = CosmosClient.from_connection_string(COSMOS_CONN)
    db_client = cosmos_client.get_database_client(COSMOS_DB)
    schedule_container = db_client.get_container_client(COSMOS_SCHEDULE_CONTAINER)
    funds_container = db_client.get_container_client(COSMOS_FUNDS_CONTAINER)
    email_client = EmailClient.from_connection_string(ACS_CONN)

    # Fetch all pending schedules for today
    query = f"SELECT * FROM c WHERE c.type='schedule' AND c.send_date='{today}' AND c.status='pending'"
    schedules = list(schedule_container.query_items(query=query, enable_cross_partition_query=True))

    if not schedules:
        logging.info("No pending scheduled emails for today.")
        return

    logging.info(f"Found {len(schedules)} scheduled email(s) for today.")

    for schedule in schedules:
        user_id = schedule.get("user_id")
        user_email = schedule.get("email")

        if not user_id or not user_email:
            logging.warning("Skipping invalid schedule record with missing user_id or email.")
            continue

        # Fetch user's fund records
        funds_query = f"SELECT * FROM c WHERE c.user_id='{user_id}'"
        fund_items = list(funds_container.query_items(query=funds_query, enable_cross_partition_query=True))

        if not fund_items:
            logging.warning(f"No fund data found for user {user_id}. Skipping email.")
            schedule["status"] = "no_data"
            schedule_container.upsert_item(schedule)
            continue

        # Filter out unwanted system fields
        exclude_fields = {"user_id", "id", "_rid", "_self", "_etag", "_attachments", "_ts"}
        filtered_items = [{k: v for k, v in item.items() if k not in exclude_fields} for item in fund_items]

        # Prepare CSV in memory
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=filtered_items[0].keys())
        writer.writeheader()
        writer.writerows(filtered_items)
        csv_data = csv_buffer.getvalue().encode("utf-8")
        csv_base64 = base64.b64encode(csv_data).decode("utf-8")

        # Build ACS email message payload
        message = {
            "senderAddress": "DoNotReply@cf856137-20fd-47dc-b563-302f54e40d38.azurecomm.net",
            "recipients": {"to": [{"address": user_email}]},
            "content": {
                "subject": f"Your Fund Data Report – {today}",
                "html": f"""
                    <p>Hello,</p>
                    <p>Your <b>fund data report</b> for <b>{today}</b> is attached as a CSV file.</p>
                    <p>Regards,<br>LP Query Team</p>
                """,
                "plainText": f"Hello,\n\nAttached is your fund data report for {today}."
            },
            "attachments": [
                {
                    "name": f"funds_{user_id}_{today}.csv",
                    "contentType": "text/csv", 
                    "contentInBase64": csv_base64
                }
            ]
        }

        try:
            poller = email_client.begin_send(message)
            result = poller.result()
            logging.info(f"✅ Email sent to {user_email} (Operation ID: {result['id']})")

            # Update schedule as sent
            schedule["status"] = "sent"
            schedule_container.upsert_item(schedule)

        except Exception as e:
            logging.error(f"❌ Failed to send email to {user_email}: {e}")
            schedule["status"] = "failed"
            schedule_container.upsert_item(schedule)
