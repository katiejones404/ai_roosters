import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_price_alert_email(
    to_email: str,
    ticker: str,
    direction: str,
    target_price: float,
    current_price: float,
) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("ALERT_FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP_USER and SMTP_PASS must be set to send alert emails.")

    direction_word = "risen above" if direction == "above" else "fallen below"
    subject = f"StockSense Alert: {ticker} has {direction_word} ${target_price:.2f}"
    body = (
        f"Your price alert for {ticker} has been triggered.\n\n"
        f"Condition:     {ticker} {direction} ${target_price:.2f}\n"
        f"Current price: ${current_price:.2f}\n\n"
        f"Log in to StockSense to review your portfolio.\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, to_email, msg.as_string())
