import asyncio
import imaplib
import smtplib
import ssl


def _test_imap(host: str, port: int, use_ssl: bool, username: str, password: str) -> None:
    if use_ssl:
        client = imaplib.IMAP4_SSL(host, port, timeout=20)
    else:
        client = imaplib.IMAP4(host, port, timeout=20)
    try:
        client.login(username, password)
        client.logout()
    finally:
        try:
            client.shutdown()
        except Exception:
            pass


def _test_smtp(
    host: str,
    port: int,
    use_ssl: bool,
    use_tls: bool,
    username: str,
    password: str,
) -> None:
    if use_ssl:
        client = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        client = smtplib.SMTP(host, port, timeout=20)
    try:
        if not use_ssl and use_tls:
            client.starttls(context=ssl.create_default_context())
        if username:
            client.login(username, password)
    finally:
        try:
            client.quit()
        except Exception:
            pass


def test_mail_connection_sync(
    *,
    imap_host: str,
    imap_port: int,
    imap_use_ssl: bool,
    smtp_host: str,
    smtp_port: int,
    smtp_use_ssl: bool,
    smtp_use_tls: bool,
    username: str,
    password: str,
) -> tuple[bool, str]:
    if not imap_host.strip() or not smtp_host.strip():
        return False, "IMAP and SMTP hostnames are required"
    if not username.strip() or not password:
        return False, "Admin username and password are required"

    try:
        _test_imap(imap_host.strip(), imap_port, imap_use_ssl, username.strip(), password)
    except Exception as exc:
        return False, f"IMAP connection failed: {exc}"

    try:
        _test_smtp(
            smtp_host.strip(),
            smtp_port,
            smtp_use_ssl,
            smtp_use_tls,
            username.strip(),
            password,
        )
    except Exception as exc:
        return False, f"SMTP connection failed: {exc}"

    return True, "Connection successful"


async def test_mail_connection(**kwargs) -> tuple[bool, str]:
    return await asyncio.to_thread(test_mail_connection_sync, **kwargs)
