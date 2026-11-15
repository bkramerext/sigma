"""Offline tests for the local feedback delivery diagnostic."""

import io
import os
import smtplib
import ssl
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import cloud_auth, feedback_diagnostic


class FeedbackDiagnosticTests(unittest.TestCase):
    def test_uses_same_feedback_mail_path_and_configured_contact(self):
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": " signer@example.org ",
                    "SIGMA_EMAIL_SMTP_USERNAME": "sender@example.org",
                    "SIGMA_EMAIL_SMTP_PASSWORD": "test-only-password",
                },
                clear=True,
            ),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch.object(cloud_auth, "_deliver_feedback") as send,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = feedback_diagnostic.run("hello world")
        self.assertEqual(status, 0)
        self.assertIn("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL: signer@example.org", output.getvalue())
        self.assertIn("ACCEPTED", output.getvalue())
        self.assertEqual(send.call_args.args[1], "hello world")
        self.assertEqual(send.call_args.kwargs["account_email"], "signer@example.org")
        self.assertEqual(send.call_args.kwargs["contact_email"], "signer@example.org")
        self.assertEqual(send.call_args.kwargs["diagnostic_recipients"], ["signer@example.org"])

    def test_smtp_transport_preserves_feedback_content(self):
        env = {
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "signed-in@example.org",
            "SIGMA_INVITATION_SMTP_USERNAME": "sender@example.org",
            "SIGMA_INVITATION_SMTP_PASSWORD": "fake-app-password",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch("sigma.cloud_auth.smtplib.SMTP") as smtp,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = feedback_diagnostic.run("hello world")
            client = smtp.return_value.__enter__.return_value
            sent = client.send_message.call_args
        self.assertEqual(status, 0)
        self.assertEqual(sent.kwargs["from_addr"], "sender@example.org")
        self.assertEqual(sent.kwargs["to_addrs"], ["signed-in@example.org"])
        body = sent.args[0].get_content()
        self.assertIn("hello world", body)
        self.assertIn("Verified account: signed-in@example.org", body)
        self.assertIn("Contact email (signed-in Google account): signed-in@example.org", body)
        self.assertNotIn("fake-app-password", output.getvalue())

    def test_forced_smtp_ignores_expired_gmail_token_setting(self):
        env = {
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "signed-in@example.org",
            "SIGMA_INVITATION_SMTP_USERNAME": "sender@example.org",
            "SIGMA_INVITATION_SMTP_PASSWORD": "fake-app-password",
            "SIGMA_INVITATION_GMAIL_TOKEN_FILE": "/missing/expired-token.json",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch("sigma.cloud_auth.smtplib.SMTP") as smtp,
            patch("sigma.gmail_delivery.send_admin_notification") as gmail,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = feedback_diagnostic.run("hello world", transport="smtp")
        self.assertEqual(status, 0)
        self.assertIn("Transport: SMTP", output.getvalue())
        smtp.assert_called_once()
        gmail.assert_not_called()

    def test_smtp_authentication_reports_code_without_server_response(self):
        env = {
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "signed-in@example.org",
            "SIGMA_EMAIL_SMTP_USERNAME": "sender@example.org",
            "SIGMA_EMAIL_SMTP_PASSWORD": "test-only-password",
        }
        rejection = smtplib.SMTPAuthenticationError(535, b"server-secret-credential-echo")
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch("sigma.cloud_auth.smtplib.SMTP") as smtp,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as errors,
        ):
            smtp.return_value.__enter__.return_value.login.side_effect = rejection
            status = feedback_diagnostic.run("hello world", transport="smtp")
        self.assertEqual(status, 1)
        output = errors.getvalue()
        self.assertIn("SMTP authentication rejected (SMTP code 535)", output)
        self.assertNotIn("server-secret-credential-echo", output)
        self.assertNotIn("test-only-password", output)

    def test_smtp_connectivity_failure_is_not_mislabeled_authentication(self):
        env = {
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "signed-in@example.org",
            "SIGMA_EMAIL_SMTP_USERNAME": "sender@example.org",
            "SIGMA_EMAIL_SMTP_PASSWORD": "test-only-password",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch("sigma.cloud_auth.smtplib.SMTP", side_effect=TimeoutError("private")),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as errors,
        ):
            status = feedback_diagnostic.run("hello world", transport="smtp")
        self.assertEqual(status, 1)
        self.assertIn("SMTP connection closed, was refused, or timed out", errors.getvalue())
        self.assertNotIn("private", errors.getvalue())

    def test_smtp_tls_failure_is_classified_without_leaking_details(self):
        env = {
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "signed-in@example.org",
            "SIGMA_EMAIL_SMTP_USERNAME": "sender@example.org",
            "SIGMA_EMAIL_SMTP_PASSWORD": "test-only-password",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch("sigma.cloud_auth.smtplib.SMTP") as smtp,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as errors,
        ):
            smtp.return_value.__enter__.return_value.starttls.side_effect = ssl.SSLError(
                "private certificate info"
            )
            status = feedback_diagnostic.run("hello world", transport="smtp")
        self.assertEqual(status, 1)
        self.assertIn("SMTP TLS handshake/certificate failed", errors.getvalue())
        self.assertNotIn("private certificate info", errors.getvalue())

    def test_gmail_cli_opens_google_auth_only_when_grant_missing(self):
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
                    "GOOGLE_OIDC_CLIENT_ID": "local-client-id",
                },
                clear=True,
            ),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch("sigma.local_gmail_cli_auth.existing_grant", return_value=None) as existing,
            patch(
                "sigma.local_gmail_cli_auth.authorize",
                return_value=(Path("/private/token.json"), "selected-google@example.org"),
            ) as authorize,
            patch.object(feedback_diagnostic, "_gmail_ready", return_value=True),
            patch.object(cloud_auth, "_deliver_feedback") as send,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = feedback_diagnostic.run("hello world", transport="gmail")
        self.assertEqual(status, 0)
        existing.assert_called_once_with()
        authorize.assert_called_once_with()
        self.assertEqual(send.call_args.kwargs["account_email"], "selected-google@example.org")
        self.assertEqual(send.call_args.kwargs["contact_email"], "selected-google@example.org")
        self.assertEqual(send.call_args.kwargs["diagnostic_recipients"], ["admin@example.org"])
        self.assertIn("Contact source: Google OAuth verified account", output.getvalue())

    def test_gmail_feedback_attachment_uses_existing_mime_delivery(self):
        with TemporaryDirectory() as directory:
            attachment = Path(directory) / "research.pdf"
            attachment.write_bytes(b"%PDF-1.7\nfixture-data")
            with (
                patch.dict(
                    os.environ,
                    {
                        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
                        "GOOGLE_OIDC_CLIENT_ID": "local-client",
                    },
                    clear=True,
                ),
                patch.object(feedback_diagnostic, "load_local_config"),
                patch(
                    "sigma.local_gmail_cli_auth.existing_grant",
                    return_value=(Path("/private/token.json"), "sender@example.org"),
                ),
                patch.object(feedback_diagnostic, "_gmail_ready", return_value=True),
                patch("sigma.gmail_delivery.send_message") as send,
                patch.object(cloud_auth, "_deliver_feedback") as old_feedback,
                redirect_stdout(io.StringIO()) as output,
            ):
                status = feedback_diagnostic.run(
                    "hello world", transport="gmail", attach=str(attachment)
                )
        self.assertEqual(status, 0)
        old_feedback.assert_not_called()
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["recipients"], ["admin@example.org"])
        outgoing = send.call_args.args[0]
        self.assertEqual(outgoing["Subject"], "New SIGMA feedback")
        self.assertNotIn("From", outgoing)
        self.assertNotIn("To", outgoing)
        body = outgoing.get_body(preferencelist=("plain",))
        self.assertIsNotNone(body)
        self.assertIn("Message:\nhello world", body.get_content())
        self.assertIn("Verified account: sender@example.org", body.get_content())
        parts = list(outgoing.iter_attachments())
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_filename(), "research.pdf")
        self.assertEqual(parts[0].get_content_type(), "application/pdf")
        self.assertEqual(parts[0].get_payload(decode=True), b"%PDF-1.7\nfixture-data")
        self.assertIn("Attachment: research.pdf", output.getvalue())

    def test_smtp_feedback_attachment_uses_existing_envelope(self):
        with TemporaryDirectory() as directory:
            attachment = Path(directory) / "notes.txt"
            attachment.write_text("hello attachment", encoding="utf-8")
            with (
                patch.dict(
                    os.environ,
                    {
                        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
                        "SIGMA_EMAIL_SMTP_USERNAME": "sender@example.org",
                        "SIGMA_EMAIL_SMTP_PASSWORD": "fixture-app-password",
                    },
                    clear=True,
                ),
                patch.object(feedback_diagnostic, "load_local_config"),
                patch("sigma.cloud_auth.smtplib.SMTP") as smtp,
                redirect_stdout(io.StringIO()),
            ):
                status = feedback_diagnostic.run(
                    "hello world", transport="smtp", attach=str(attachment)
                )
                sent = smtp.return_value.__enter__.return_value.send_message.call_args
        self.assertEqual(status, 0)
        self.assertEqual(sent.kwargs["from_addr"], "sender@example.org")
        self.assertEqual(sent.kwargs["to_addrs"], ["admin@example.org"])
        outgoing = sent.args[0]
        self.assertEqual(outgoing["Subject"], "New SIGMA feedback")
        parts = list(outgoing.iter_attachments())
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_filename(), "notes.txt")
        self.assertEqual(parts[0].get_payload(decode=True), b"hello attachment")

    def test_invalid_attachment_aborts_before_google_auth_or_mail(self):
        with (
            patch.dict(
                os.environ, {"SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org"}, clear=True
            ),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch("sigma.local_gmail_cli_auth.authorize") as authorize,
            patch.object(cloud_auth, "_deliver_feedback") as feedback,
            redirect_stderr(io.StringIO()) as errors,
        ):
            status = feedback_diagnostic.run(
                "hello world", transport="gmail", attach="/definitely/not/a/valid/sigma-file.pdf"
            )
        self.assertEqual(status, 2)
        self.assertIn("Attachment must be an existing regular file", errors.getvalue())
        authorize.assert_not_called()
        feedback.assert_not_called()

    def test_attachment_size_limit_applies_before_google_auth(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "large.bin"
            path.write_bytes(b"0123456789ABCDEF")
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(feedback_diagnostic, "load_local_config"),
                patch.object(feedback_diagnostic, "MAX_FEEDBACK_ATTACHMENT_BYTES", 10),
                patch("sigma.local_gmail_cli_auth.authorize") as authorize,
                patch("sigma.gmail_delivery.send_message") as send,
                redirect_stderr(io.StringIO()) as errors,
            ):
                status = feedback_diagnostic.run("hello world", transport="gmail", attach=str(path))
        self.assertEqual(status, 2)
        self.assertIn("18 MB email attachment limit", errors.getvalue())
        authorize.assert_not_called()
        send.assert_not_called()

    def test_missing_contact_fails_before_sending(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch.object(cloud_auth, "_deliver_feedback") as send,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = feedback_diagnostic.run("hello world")
        self.assertEqual(status, 2)
        self.assertIn("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL", output.getvalue())
        self.assertIn("RESULT: NOT SENT", output.getvalue())
        send.assert_not_called()

    def test_rejects_invalid_feedback_before_sending(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch.object(cloud_auth, "_deliver_feedback") as send,
            redirect_stderr(io.StringIO()),
        ):
            status = feedback_diagnostic.run("short")
        self.assertEqual(status, 2)
        send.assert_not_called()

    def test_missing_smtp_settings_explain_exact_environment_variables(self):
        with (
            patch.dict(
                os.environ, {"SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "you@example.org"}, clear=True
            ),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch.object(cloud_auth, "_deliver_feedback") as send,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = feedback_diagnostic.run("hello world", transport="smtp")
        self.assertEqual(status, 2)
        rendered = output.getvalue()
        self.assertIn("[MISSING] SIGMA_EMAIL_SMTP_USERNAME", rendered)
        self.assertIn("[MISSING] SIGMA_EMAIL_SMTP_PASSWORD_FILE", rendered)
        self.assertIn("Gmail app password, NOT the normal account password", rendered)
        self.assertIn("RESULT: NOT SENT", rendered)
        send.assert_not_called()

    def test_smtp_file_missing_is_diagnosed_without_attempting_send(self):
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "you@example.org",
                    "SIGMA_EMAIL_SMTP_USERNAME": "sender@example.org",
                    "SIGMA_EMAIL_SMTP_PASSWORD_FILE": "/nonexistent/test-sigma-app-password",
                },
                clear=True,
            ),
            patch.object(feedback_diagnostic, "load_local_config"),
            patch.object(cloud_auth, "_deliver_feedback") as send,
            redirect_stdout(io.StringIO()) as output,
        ):
            status = feedback_diagnostic.run("hello world", transport="smtp")
        self.assertEqual(status, 2)
        self.assertIn("file not found", output.getvalue())
        self.assertNotIn("BEGIN PRIVATE KEY", output.getvalue())
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
