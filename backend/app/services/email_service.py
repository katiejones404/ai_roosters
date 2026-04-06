"""
Notes - Email utilities for StockSense.
Handles price alert emails and password reset messages using SMTP settings.
"""



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

    deployedURL = "https://ai-roosters-webpage.vercel.app/"
    textEntry = "Log in to StockSense"
    direction_word = "risen above" if direction == "above" else "fallen below"
    subject = f"StockSense Alert: {ticker} has {direction_word} ${target_price:.2f}"
    text_body = (
        f"Your price alert for {ticker} has been triggered.\n\n"
        f"Condition: {ticker} {direction} ${target_price:.2f}\n"
        f"Current price: ${current_price:.2f}\n\n"
        f"{textEntry}: {deployedURL}\n"
        f"to review your portfolio."
    )

    html_body = (
        f"Your price alert for {ticker} has been triggered.<br><br>"
        f"Condition: {ticker} {direction} ${target_price:.2f}<br>"
        f"Current price: ${current_price:.2f}<br><br>"
        f'<a href="{deployedURL}">{textEntry}</a> to review your portfolio.'
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, to_email, msg.as_string())


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """
    Send a password reset email with a time-limited reset link.

    Parameters
    ----------
    to_email : str
        Recipient email address.
    reset_link : str
        Full URL the user should visit to reset their password.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("ALERT_FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP_USER and SMTP_PASS must be set to send password reset emails.")

    subject = "StockSense: Reset Your Password"
    body = (
        "We received a request to reset your StockSense password.\n\n"
        "Click the link below to set a new password. This link expires in 15 minutes.\n\n"
        f"{reset_link}\n\n"
        "If you did not request a password reset, you can ignore this email. "
        "Your password will not be changed.\n"
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
