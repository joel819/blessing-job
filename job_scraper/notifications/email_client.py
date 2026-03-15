import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Recommendation: Store these in environment variables or a config file
EMAIL_ADDRESS = os.environ.get("EMAIL_USERNAME", "joeljobbot@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "drsa rbrx oiee jjas")
RECEIVER_EMAIL = os.environ.get("EMAIL_RECIPIENT", "joeljobbot@gmail.com")

def send_email(subject, body):
    """
    Send an email notification via Gmail SMTP.
    
    Args:
        subject (str): The email subject line.
        body (str): The email body content (HTML supported).
    """
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = RECEIVER_EMAIL
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "html"))

    try:
        # Using Gmail SMTP with STARTTLS on port 587
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")
