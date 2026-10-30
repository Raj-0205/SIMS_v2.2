# tests/test_upi_dynamic_qr_and_verification.py

from __future__ import annotations
import unittest
from unittest.mock import MagicMock
import flet as ft

from core.utils.upi_qr import build_upi_deep_link, generate_upi_qr_base64
from core.exceptions import ValidationError
from modules.payments.service import PaymentService
from modules.payments.dto import PaymentCreateDTO
from modules.settings.service import SettingsService
from modules.admission.controller import AdmissionController
from modules.admission.views.payment_dialog import PaymentDialog
from modules.receipts.controller import ReceiptController
from modules.admission.views.receipt_dialog import ReceiptDialog
from infrastructure.pdf.receipt_generator import ReceiptPDFGenerator
from core.security.context import SecurityContext
from core.security.roles import Role


class TestUPIDynamicQRAndVerification(unittest.TestCase):
    """
    Test suite for Dynamic UPI QR Code Generation, Anti-Fraud Payment Verification,
    and PaymentDialog UI integration.
    """

    @classmethod
    def setUpClass(cls):
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)

    def setUp(self):
        self.adm_ctrl = AdmissionController()
        self.pay_service = PaymentService()
        self.settings_service = SettingsService()
        self.receipt_ctrl = ReceiptController()

    def test_01_upi_deep_link_formatting(self):
        """Verify NPCI-compliant UPI deep link format with custom amounts and notes."""
        link_5000 = build_upi_deep_link(
            upi_id="9271226772@yescred",
            payee_name="Sudharm Infotech",
            amount=5000.0,
            transaction_note="Fee - Rahul Sharma (2026-001)",
        )
        self.assertIn("pa=9271226772@yescred", link_5000)
        self.assertIn("pn=Sudharm%20Infotech", link_5000)
        self.assertIn("am=5000.00", link_5000)
        self.assertIn("cu=INR", link_5000)
        self.assertIn("tn=Fee%20-%20Rahul%20Sharma%20%282026-001%29", link_5000)

        # Test with ₹3000
        link_3000 = build_upi_deep_link(
            upi_id="9271226772@yescred",
            payee_name="Sudharm Infotech",
            amount=3000.0,
        )
        self.assertIn("am=3000.00", link_3000)
        self.assertTrue(link_3000.startswith("upi://pay?"))

    def test_02_upi_qr_generation(self):
        """Verify Base64 PNG QR code generation with exact amounts."""
        b64_5000, link_5000 = generate_upi_qr_base64(
            upi_id="9271226772@yescred",
            payee_name="Sudharm Infotech",
            amount=5000.0,
            transaction_note="Admission Fee",
        )
        self.assertIsInstance(b64_5000, str)
        self.assertGreater(len(b64_5000), 500)
        self.assertIn("am=5000.00", link_5000)

        b64_3000, link_3000 = generate_upi_qr_base64(
            upi_id="9271226772@yescred",
            payee_name="Sudharm Infotech",
            amount=3000.0,
            transaction_note="Admission Fee",
        )
        self.assertNotEqual(b64_5000, b64_3000)
        self.assertIn("am=3000.00", link_3000)

    def test_03_settings_upi_configuration(self):
        """Verify SettingsService stores and returns default and custom UPI details."""
        profile = self.settings_service.get_institute_profile()
        self.assertEqual(profile.get("upi_id"), "9271226772@yescred")
        self.assertEqual(profile.get("upi_payee_name"), "Sudharm Infotech")

    def test_04_payment_service_anti_fraud_dummy_rejection(self):
        """Verify PaymentService rejects dummy / invalid transaction references."""
        # Create an admission for test
        adm_id = self.adm_ctrl.create_admission({
            "first_name": "UPI",
            "last_name": "TestStudent",
            "village": "Chandwad",
            "course_id": 1,
            "agreed_fee": 10000.0,
            "discount": 0.0,
            "mobile_number": "9898989801",
            "secondary_mobile": "9898989891",
        })
        adm = self.adm_ctrl.get_admission(adm_id)

        # Reject dummy ref "1234"
        with self.assertRaises(ValidationError) as ctx:
            self.pay_service.record_payment(PaymentCreateDTO(
                admission_id=adm_id,
                student_id=adm.student_id,
                amount=1000.0,
                payment_mode="UPI",
                collector_name="Admin",
                transaction_ref="1234",
            ))
        self.assertIn("Invalid Transaction Reference", str(ctx.exception))

        # Reject dummy ref "test"
        with self.assertRaises(ValidationError) as ctx:
            self.pay_service.record_payment(PaymentCreateDTO(
                admission_id=adm_id,
                student_id=adm.student_id,
                amount=1000.0,
                payment_mode="UPI",
                collector_name="Admin",
                transaction_ref="test",
            ))
        self.assertIn("Invalid Transaction Reference", str(ctx.exception))

    def test_05_payment_service_duplicate_utr_replay_attack(self):
        """Verify PaymentService prevents double-spending / duplicate UTR replay."""
        adm_id1 = self.adm_ctrl.create_admission({
            "first_name": "First",
            "last_name": "Student",
            "village": "Chandwad",
            "course_id": 1,
            "agreed_fee": 8000.0,
            "mobile_number": "9898989802",
            "secondary_mobile": "9898989892",
        })
        adm1 = self.adm_ctrl.get_admission(adm_id1)

        unique_utr = "430299887711"
        # First payment succeeds
        pay1 = self.pay_service.record_payment(PaymentCreateDTO(
            admission_id=adm_id1,
            student_id=adm1.student_id,
            amount=2000.0,
            payment_mode="UPI",
            collector_name="Admin",
            transaction_ref=unique_utr,
        ))
        self.assertGreater(pay1, 0)

        # Second payment attempting to reuse same UTR MUST be rejected
        adm_id2 = self.adm_ctrl.create_admission({
            "first_name": "Second",
            "last_name": "Student",
            "village": "Chandwad",
            "course_id": 1,
            "agreed_fee": 8000.0,
            "mobile_number": "9898989803",
            "secondary_mobile": "9898989893",
        })
        adm2 = self.adm_ctrl.get_admission(adm_id2)

        with self.assertRaises(ValidationError) as ctx:
            self.pay_service.record_payment(PaymentCreateDTO(
                admission_id=adm_id2,
                student_id=adm2.student_id,
                amount=2000.0,
                payment_mode="UPI",
                collector_name="Admin",
                transaction_ref=unique_utr,
            ))
        self.assertIn("Duplicate payment reference cannot be reused", str(ctx.exception))

        # Case-insensitive reuse MUST also be rejected
        with self.assertRaises(ValidationError) as ctx:
            self.pay_service.record_payment(PaymentCreateDTO(
                admission_id=adm_id2,
                student_id=adm2.student_id,
                amount=2000.0,
                payment_mode="UPI",
                collector_name="Admin",
                transaction_ref=unique_utr.lower(),
            ))
        self.assertIn("Duplicate payment reference cannot be reused", str(ctx.exception))

    def test_06_payment_dialog_dynamic_qr_and_verification(self):
        """Verify PaymentDialog UI dynamically changes QR on amount change and enforces UTR."""
        adm_id = self.adm_ctrl.create_admission({
            "first_name": "Dialog",
            "last_name": "Student",
            "village": "Chandwad",
            "course_id": 1,
            "agreed_fee": 12000.0,
            "mobile_number": "9898989804",
            "secondary_mobile": "9898989894",
        })
        adm = self.adm_ctrl.get_admission(adm_id)

        mock_page = MagicMock()
        dialog = PaymentDialog(
            admission_id=adm_id,
            student_name=adm.student_name,
            course_name=adm.course_name,
            candidate_number=adm.admission_number,
            total_fee=12000.0,
            already_paid=0.0,
            default_amount=5000.0,
            page=mock_page,
        )

        # Default UPI config
        self.assertEqual(dialog.upi_id, "9271226772@yescred")
        self.assertEqual(dialog.upi_payee_name, "Sudharm Infotech")

        # Initial amount ₹5,000 QR generated
        self.assertTrue(dialog.upi_qr_image.src.startswith("data:image/png;base64,"))
        self.assertEqual(dialog.upi_amount_badge.value, "₹5,000.00")
        self.assertIn("am=5000.00", dialog._latest_upi_link)

        # Switch mode to UPI
        dialog.mode_dropdown.value = "UPI"
        dialog._handle_mode_change()
        self.assertTrue(dialog.upi_helper_container.visible)
        self.assertIn("Bank UTR", dialog.tx_ref_input.label)

        # Change amount to 3000 dynamically
        dialog.amount_input.value = "3000"
        dialog._handle_amount_change(None)
        self.assertEqual(dialog.upi_amount_badge.value, "₹3,000.00")
        self.assertIn("am=3000.00", dialog._latest_upi_link)

        # Change amount using quick chip ₹1,000
        dialog._set_quick_amount(1000.0)
        self.assertEqual(dialog.amount_input.value, "1000")
        self.assertEqual(dialog.upi_amount_badge.value, "₹1,000.00")
        self.assertIn("am=1000.00", dialog._latest_upi_link)

        # Verify confirmation without UTR is rejected in UI
        dialog.pin_input.value = "1234"
        dialog.tx_ref_input.value = ""
        dialog.handle_confirm_payment(None)
        self.assertTrue(dialog.error_container.visible)
        self.assertIn("Bank UTR / UPI Reference Number is mandatory", dialog.error_text.value)

        # Verify confirmation with dummy UTR is rejected in UI
        dialog.tx_ref_input.value = "12345"
        dialog.handle_confirm_payment(None)
        self.assertTrue(dialog.error_container.visible)
        self.assertIn("Invalid UTR Reference", dialog.error_text.value)

        # Verify confirmation with valid UTR succeeds
        valid_utr = "430299887766"
        dialog.tx_ref_input.value = valid_utr
        dialog.amount_input.value = "1000"
        dialog.handle_confirm_payment(None)

        # Admission should now be confirmed with total_paid = 1000
        updated_adm = self.adm_ctrl.get_admission(adm_id)
        self.assertEqual(updated_adm.total_paid, 1000.0)
        status_val = updated_adm.status.value if hasattr(updated_adm.status, "value") else str(updated_adm.status)
        self.assertEqual(status_val, "CONFIRMED")

    def test_07_receipt_utr_printing_and_dialog_display(self):
        """Verify UTR is mentioned on ReceiptDTO, ReceiptDialog UI, WhatsApp text, and PDF receipt."""
        from unittest.mock import patch
        from pathlib import Path

        adm_id = self.adm_ctrl.create_admission({
            "first_name": "Rohan",
            "last_name": "Patil",
            "village": "Chandwad",
            "course_id": 1,
            "agreed_fee": 15000.0,
            "mobile_number": "9898989805",
            "secondary_mobile": "9898989895",
        })
        adm = self.adm_ctrl.get_admission(adm_id)

        utr_12_digits = "430211223344"
        pay_id = self.pay_service.record_payment(PaymentCreateDTO(
            admission_id=adm_id,
            student_id=adm.student_id,
            amount=5000.0,
            payment_mode="UPI",
            collector_name="Admin",
            transaction_ref=utr_12_digits,
        ))

        # 1. Verify ReceiptDTO has transaction_ref populated
        receipt = self.receipt_ctrl.get_receipt_by_payment(pay_id)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.transaction_ref, utr_12_digits)

        # 2. Verify ReceiptDialog has transaction_ref and renders UTR row
        dialog = ReceiptDialog(
            receipt=receipt,
            student_name=adm.student_name,
            candidate_number=adm.admission_number,
            course_name=adm.course_name,
            mobile_number=adm.mobile_number,
        )
        self.assertEqual(dialog.transaction_ref, utr_12_digits)

        # 3. Verify WhatsApp message contains Bank UTR / Ref
        with patch("webbrowser.open") as mock_wb:
            dialog.handle_whatsapp(None)
            mock_wb.assert_called_once()
            wa_url = mock_wb.call_args[0][0]
            self.assertIn("Bank", wa_url)
            self.assertIn(utr_12_digits, wa_url)

        # 4. Verify PDF receipt generator renders vector receipt with UTR
        test_pdf_path = Path("/tmp/test_receipt_utr.pdf")
        if test_pdf_path.exists():
            test_pdf_path.unlink()

        ReceiptPDFGenerator.generate_receipt_pdf(
            receipt_data={
                "receipt_number": receipt.receipt_number,
                "student_name": adm.student_name,
                "student_id": adm.student_id,
                "candidate_number": adm.admission_number,
                "course_name": adm.course_name,
                "installment_number": 1,
                "amount_paid": 5000.0,
                "total_course_fee": 15000.0,
                "total_paid_till_now": 5000.0,
                "pending_amount": 10000.0,
                "payment_mode": "UPI",
                "collector_name": "Admin",
                "transaction_ref": utr_12_digits,
            },
            output_path=test_pdf_path,
        )
        self.assertTrue(test_pdf_path.exists())
        self.assertGreater(test_pdf_path.stat().st_size, 500)


if __name__ == "__main__":
    unittest.main()
