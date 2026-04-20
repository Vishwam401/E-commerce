from fastapi_mail import ConnectionConfig, FastMail, MessageType, MessageSchema
from app.core.config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True
)


async def send_verification_email(email_to: str, token: str):
    base_url = settings.EMAIL_VERIFY_BASE_URL.rstrip("/")
    verify_link = f"{base_url}/auth/verify?token={token}"

    html = f"""
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#111827;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
            <tr>
              <td style="padding:24px 28px;background:#111827;color:#ffffff;font-size:20px;font-weight:700;">
                Pro E-commerce API
              </td>
            </tr>
            <tr>
              <td style="padding:28px;line-height:1.6;">
                <h2 style="margin:0 0 12px 0;font-size:22px;color:#111827;">Verify your email address</h2>
                <p style="margin:0 0 16px 0;color:#374151;font-size:15px;">
                  Thanks for signing up. Please confirm your email to activate your account and continue securely.
                </p>
                <p style="margin:0 0 24px 0;">
                  <a href="{verify_link}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:8px;">
                    Verify Email
                  </a>
                </p>
                <p style="margin:0 0 8px 0;color:#6b7280;font-size:13px;">
                  If the button does not work, copy and paste this link into your browser:
                </p>
                <p style="margin:0;word-break:break-all;font-size:13px;">
                  <a href="{verify_link}" style="color:#2563eb;text-decoration:underline;">{verify_link}</a>
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px;">
                If you did not create this account, you can safely ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
    """

    message = MessageSchema(
        subject="Verify your email address",
        recipients=[email_to],
        body=html,
        subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message)