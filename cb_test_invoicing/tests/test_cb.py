# Copyright 2017 Creu Blanca
# Copyright 2017 Eficent Business and IT Consulting Services, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from odoo import fields
from odoo.addons.cb_test.tests.test_cb import TestCB
from odoo.exceptions import ValidationError


class TestCBSale(TestCB):
    def test_multiple_groups(self):
        method = self.browse_ref("cb_medical_careplan_sale.by_patient")
        method_2 = self.browse_ref("cb_medical_careplan_sale.by_customer")
        auth_method = self.env["medical.authorization.method"].create(
            {
                "name": "Testing authorization_method",
                "code": "none",
                "invoice_group_method_id": method_2.id,
                "always_authorized": True,
            }
        )
        self.agreement_line.write(
            {
                "authorization_method_id": auth_method.id,
                "coverage_percentage": 100,
            }
        )
        self.plan_definition2.third_party_bill = False
        self.plan_definition.is_breakdown = True
        self.plan_definition.is_billable = True
        self.agreement.invoice_group_method_id = method
        self.agreement_line3.coverage_percentage = 100
        self.company.sale_merge_draft_invoice = True
        for i in range(1, 10):
            encounter, careplan, group = self.create_careplan_and_group(
                self.agreement_line3
            )
            self.assertTrue(group.procedure_request_ids)
            self.assertTrue(
                group.is_sellable_insurance or group.is_sellable_private
            )
            self.assertEqual(method, group.invoice_group_method_id)
            self.assertFalse(
                self.env["medical.request.group"].search(
                    [
                        ("encounter_id", "=", encounter.id),
                        ("careplan_id", "=", careplan.id),
                        ("invoice_group_method_id", "=", method_2.id),
                    ]
                )
            )
            wizard = self.env["medical.careplan.add.plan.definition"].create(
                {
                    "careplan_id": careplan.id,
                    "agreement_line_id": self.agreement_line.id,
                }
            )
            self.assertIn(self.agreement, wizard.agreement_ids)
            self.action.is_billable = False
            wizard.run()
            self.assertFalse(group.third_party_bill)
            self.assertTrue(
                self.env["medical.request.group"].search(
                    [
                        ("encounter_id", "=", encounter.id),
                        ("careplan_id", "=", careplan.id),
                        ("invoice_group_method_id", "=", method_2.id),
                    ]
                )
            )
            self.env["wizard.medical.encounter.close"].create(
                {
                    "encounter_id": encounter.id,
                    "pos_session_id": self.session.id,
                }
            ).run()
            self.assertTrue(encounter.sale_order_ids)
            sale_order = encounter.sale_order_ids
            self.assertFalse(sale_order.third_party_order)
            for line in sale_order.order_line:
                self.assertFalse(line.agents)
        self.session.action_pos_session_close()
        self.assertTrue(self.session.request_group_ids)
        self.assertEqual(
            self.session.encounter_ids,
            self.env["medical.encounter"].search(
                self.session.action_view_non_validated_encounters()["domain"]
            ),
        )
        non_validated = len(self.session.encounter_ids)
        for encounter in self.session.encounter_ids:
            self.assertEqual(
                non_validated, self.session.encounter_non_validated_count
            )
            encounter_aux = self.env["medical.encounter"].browse(
                self.session.open_validation_encounter(
                    encounter.internal_identifier
                )["res_id"]
            )
            action = self.session.action_view_non_validated_encounters()
            if non_validated > 1:
                self.assertIn(
                    encounter,
                    self.env["medical.encounter"].search(action["domain"]),
                )
            else:
                self.assertEqual(
                    encounter,
                    self.env["medical.encounter"].browse(action["res_id"]),
                )
            encounter_aux.admin_validate()
            non_validated -= 1
            self.assertEqual(
                non_validated, self.session.encounter_non_validated_count
            )
            for sale_order in encounter_aux.sale_order_ids:
                self.assertTrue(sale_order.invoice_ids)
                self.assertTrue(
                    all(i.state == "open" for i in sale_order.invoice_ids)
                )
                self.assertFalse(
                    all(line.invoice_lines for line in sale_order.order_line)
                )
        self.assertEqual(0, non_validated)
        self.assertEqual(0, self.session.encounter_non_validated_count)
        wzd = self.env["invoice.sales.by.group"].create(
            {
                "invoice_group_method_id": method_2.id,
                "customer_ids": [(4, self.payor.id)],
                "date_to": fields.Date.to_string(
                    fields.Date.from_string(fields.Date.today())
                    + relativedelta(days=1)
                ),
            }
        )
        wzd.invoice_sales_by_group()
        for encounter in self.session.encounter_ids:
            for sale_order in encounter.sale_order_ids:
                self.assertTrue(
                    all(line.invoice_lines for line in sale_order.order_line)
                )

    def test_validation(self):
        method = self.browse_ref("cb_medical_careplan_sale.by_preinvoicing")
        self.plan_definition2.third_party_bill = False
        self.plan_definition.is_breakdown = True
        self.plan_definition.is_billable = True
        self.agreement.invoice_group_method_id = method
        self.agreement_line3.coverage_percentage = 100
        self.agreement_line3.authorization_method_id = self.method
        self.company.sale_merge_draft_invoice = True
        encounter, careplan, group = self.create_careplan_and_group(
            self.agreement_line3
        )
        self.assertTrue(group.procedure_request_ids)
        self.assertTrue(
            group.is_sellable_insurance or group.is_sellable_private
        )
        self.assertFalse(group.third_party_bill)
        self.env["wizard.medical.encounter.close"].create(
            {"encounter_id": encounter.id, "pos_session_id": self.session.id}
        ).run()
        self.assertTrue(encounter.sale_order_ids)
        self.session.action_pos_session_close()
        self.pos_config.write({"session_sequence_prefix": "POS"})
        self.assertTrue(self.pos_config.session_sequence_id)
        self.assertEqual(
            self.pos_config.session_sequence_id.prefix, "POS/%(range_y)s/"
        )
        self.pos_config.write({"session_sequence_prefix": "PS"})
        self.assertTrue(self.pos_config.session_sequence_id)
        self.assertEqual(
            self.pos_config.session_sequence_id.prefix, "PS/%(range_y)s/"
        )
        self.pos_config.open_session_cb()
        self.assertTrue(self.session.request_group_ids)
        self.assertFalse(encounter.is_preinvoiced)
        line = encounter.sale_order_ids.order_line
        with self.assertRaises(ValidationError):
            encounter.admin_validate()
        encounter.toggle_is_preinvoiced()
        self.assertTrue(encounter.is_preinvoiced)
        self.coverage_template.write(
            {"subscriber_required": True, "subscriber_format": "^1.*$"}
        )
        with self.assertRaises(ValidationError):
            encounter.admin_validate()
        line.write({"subscriber_id": "23"})
        with self.assertRaises(ValidationError):
            encounter.admin_validate()
        line.write({"subscriber_id": "123"})
        self.agreement_line3.write(
            {
                "authorization_format_id": self.format.id,
                "authorization_method_id": self.method.id,
            }
        )
        action = (
            self.env["medical.request.group.check.authorization"]
            .with_context(line.check_authorization_action()["context"])
            .create({"authorization_number": "1234A"})
        )
        action.run()
        self.assertNotEqual(line.authorization_status, "authorized")
        self.assertEqual(line.authorization_number, "1234A")
        with self.assertRaises(ValidationError):
            encounter.admin_validate()
        action = (
            self.env["medical.request.group.check.authorization"]
            .with_context(line.check_authorization_action()["context"])
            .create({"authorization_number": "1234"})
        )
        action.run()
        self.assertEqual(line.authorization_status, "authorized")
        self.assertEqual(line.authorization_number, "1234")
        self.agreement_line3.write(
            {"authorization_format_id": self.format_letter.id}
        )
        with self.assertRaises(ValidationError):
            encounter.admin_validate()
        self.agreement_line3.write({"authorization_format_id": self.format.id})
        encounter.admin_validate()

    def test_patient_invoice(self):
        method = self.browse_ref("cb_medical_careplan_sale.by_patient")
        self.plan_definition2.third_party_bill = False
        self.plan_definition.is_breakdown = True
        self.plan_definition.is_billable = True
        self.agreement.invoice_group_method_id = method
        self.agreement_line3.coverage_percentage = 100
        self.company.sale_merge_draft_invoice = True
        for i in range(1, 10):
            encounter, careplan, group = self.create_careplan_and_group(
                self.agreement_line3
            )
            self.assertTrue(group.procedure_request_ids)
            self.assertTrue(
                group.is_sellable_insurance or group.is_sellable_private
            )
            self.assertFalse(group.third_party_bill)
            self.env["wizard.medical.encounter.close"].create(
                {
                    "encounter_id": encounter.id,
                    "pos_session_id": self.session.id,
                }
            ).run()
            self.assertTrue(encounter.sale_order_ids)
            sale_order = encounter.sale_order_ids
            self.assertFalse(sale_order.third_party_order)
            for line in sale_order.order_line:
                self.assertFalse(line.agents)
        self.session.action_pos_session_close()
        self.assertTrue(self.session.request_group_ids)
        self.assertEqual(
            self.session.encounter_ids,
            self.env["medical.encounter"].search(
                self.session.action_view_non_validated_encounters()["domain"]
            ),
        )
        non_validated = len(self.session.encounter_ids)
        for encounter in self.session.encounter_ids:
            self.assertEqual(
                non_validated, self.session.encounter_non_validated_count
            )
            encounter_aux = self.env["medical.encounter"].browse(
                self.session.open_validation_encounter(
                    encounter.internal_identifier
                )["res_id"]
            )
            action = self.session.action_view_non_validated_encounters()
            if non_validated > 1:
                self.assertIn(
                    encounter,
                    self.env["medical.encounter"].search(action["domain"]),
                )
            else:
                self.assertEqual(
                    encounter,
                    self.env["medical.encounter"].browse(action["res_id"]),
                )
            encounter_aux.admin_validate()
            non_validated -= 1
            self.assertEqual(
                non_validated, self.session.encounter_non_validated_count
            )
            for sale_order in encounter_aux.sale_order_ids:
                self.assertTrue(sale_order.invoice_ids)
                self.assertTrue(
                    all(i.state == "open" for i in sale_order.invoice_ids)
                )
        self.assertEqual(0, non_validated)
        self.assertEqual(0, self.session.encounter_non_validated_count)

    def test_no_invoice(self):
        method = self.browse_ref("cb_medical_careplan_sale.no_invoice")
        self.plan_definition2.third_party_bill = False
        self.plan_definition.is_breakdown = True
        self.plan_definition.is_billable = True
        self.agreement.invoice_group_method_id = method
        self.agreement_line3.coverage_percentage = 100
        self.company.sale_merge_draft_invoice = True
        sale_orders = self.env["sale.order"]
        for i in range(1, 10):
            encounter, careplan, group = self.create_careplan_and_group(
                self.agreement_line3
            )
            self.assertTrue(group.procedure_request_ids)
            self.assertTrue(
                group.is_sellable_insurance or group.is_sellable_private
            )
            self.assertFalse(group.third_party_bill)
            self.env["wizard.medical.encounter.close"].create(
                {
                    "encounter_id": encounter.id,
                    "pos_session_id": self.session.id,
                }
            ).run()
            self.assertTrue(encounter.sale_order_ids)
            sale_order = encounter.sale_order_ids
            self.assertFalse(sale_order.third_party_order)
            for line in sale_order.order_line:
                self.assertFalse(line.agents)
            sale_orders |= sale_order
        self.session.action_pos_session_close()
        self.assertTrue(self.session.request_group_ids)
        for encounter in self.session.encounter_ids:
            encounter_aux = self.env["medical.encounter"].browse(
                self.session.open_validation_encounter(
                    encounter.internal_identifier
                )["res_id"]
            )
            encounter_aux.admin_validate()
        for line in sale_orders.mapped("order_line"):
            self.assertEqual(line.qty_to_invoice, 0)
        for encounter in self.session.encounter_ids:
            for request in encounter.careplan_ids.mapped(
                "procedure_request_ids"
            ):
                request.draft2active()
                self.assertEqual(request.center_id, encounter.center_id)
                procedure = request.generate_event()
                procedure.performer_id = self.practitioner_01
                procedure.commission_agent_id = self.practitioner_01
                procedure.performer_id = self.practitioner_02
                procedure._onchange_performer_id()
                self.assertEqual(
                    procedure.commission_agent_id, self.practitioner_02
                )
            encounter.recompute_commissions()
            for line in encounter.sale_order_ids.mapped("order_line"):
                self.assertTrue(line.agents)
        # Settle the payments
        wizard = self.env["sale.commission.no.invoice.make.settle"].create(
            {
                "date_to": (
                    fields.Datetime.from_string(fields.Datetime.now())
                    + relativedelta(months=1)
                )
            }
        )
        settlements = self.env["sale.commission.settlement"].browse(
            wizard.action_settle()["domain"][0][2]
        )
        self.assertTrue(settlements)
        for encounter in self.session.encounter_ids:
            for request in encounter.careplan_ids.mapped(
                "procedure_request_ids"
            ):
                procedure = request.procedure_ids
                self.assertEqual(len(procedure.sale_agent_ids), 1)
                self.assertEqual(len(procedure.invoice_agent_ids), 0)
                procedure.performer_id = self.practitioner_01
                procedure.commission_agent_id = self.practitioner_01
                procedure.check_commission()
                self.assertEqual(len(procedure.sale_agent_ids), 3)
                self.assertEqual(len(procedure.invoice_agent_ids), 0)

    def test_monthly_invoice(self):
        method = self.browse_ref("cb_medical_careplan_sale.by_customer")
        self.plan_definition2.third_party_bill = False
        self.plan_definition.is_breakdown = True
        self.plan_definition.is_billable = True
        self.agreement.invoice_group_method_id = method
        self.agreement_line3.coverage_percentage = 100
        nomenclature_product = self.env["product.nomenclature.product"].create(
            {
                "nomenclature_id": self.nomenclature.id,
                "product_id": self.agreement_line3.product_id.id,
                "name": "nomenclature_name",
                "code": "nomenclature_code",
            }
        )
        self.company.sale_merge_draft_invoice = True
        sale_orders = self.env["sale.order"]
        for i in range(1, 10):
            encounter, careplan, group = self.create_careplan_and_group(
                self.agreement_line3
            )
            self.assertTrue(group.procedure_request_ids)
            self.assertTrue(
                group.is_sellable_insurance or group.is_sellable_private
            )
            self.assertFalse(group.third_party_bill)
            self.env["wizard.medical.encounter.close"].create(
                {
                    "encounter_id": encounter.id,
                    "pos_session_id": self.session.id,
                }
            ).run()
            self.assertTrue(encounter.sale_order_ids)
            sale_order = encounter.sale_order_ids
            self.assertFalse(sale_order.third_party_order)
            for line in sale_order.order_line:
                self.assertFalse(line.agents)
            sale_orders |= sale_order
        self.session.action_pos_session_close()
        self.assertTrue(self.session.request_group_ids)
        for encounter in self.session.encounter_ids:
            encounter_aux = self.env["medical.encounter"].browse(
                self.session.open_validation_encounter(
                    encounter.internal_identifier
                )["res_id"]
            )
            encounter_aux.admin_validate()
        action = (
            self.env["invoice.sales.by.group"]
            .create({"invoice_group_method_id": method.id})
            .invoice_sales_by_group()
        )
        self.assertFalse(action)
        action = (
            self.env["invoice.sales.by.group"]
            .create(
                {
                    "invoice_group_method_id": method.id,
                    "customer_ids": [(4, self.payor.id)],
                    "date_to": fields.Date.to_string(
                        fields.Date.from_string(fields.Date.today())
                        + timedelta(days=1)
                    ),
                }
            )
            .invoice_sales_by_group()
        )
        self.assertTrue(action.get("res_id", False))
        invoice = self.env["account.invoice"].browse(
            action.get("res_id", False)
        )
        invoice.action_invoice_open()
        for line in invoice.invoice_line_ids:
            self.assertEqual(line.name, nomenclature_product.name)
        for sale_order in sale_orders:
            self.assertTrue(sale_order.invoice_status == "invoiced")
        for encounter in self.session.encounter_ids:
            for request in encounter.careplan_ids.mapped(
                "procedure_request_ids"
            ):
                request.draft2active()
                self.assertEqual(request.center_id, encounter.center_id)
                procedure = request.generate_event()
                procedure.performer_id = self.practitioner_01
                procedure.commission_agent_id = self.practitioner_01
                procedure.performer_id = self.practitioner_02
                procedure._onchange_performer_id()
                self.assertEqual(
                    procedure.commission_agent_id, self.practitioner_02
                )
            encounter.recompute_commissions()
            for line in encounter.sale_order_ids.mapped("order_line"):
                self.assertTrue(line.agents)
        # Settle the payments
        wizard = self.env["sale.commission.make.settle"].create(
            {
                "date_to": (
                    fields.Datetime.from_string(fields.Datetime.now())
                    + relativedelta(months=1)
                )
            }
        )
        settlements = self.env["sale.commission.settlement"].browse(
            wizard.action_settle()["domain"][0][2]
        )
        self.assertTrue(settlements)
        for encounter in self.session.encounter_ids:
            for request in encounter.careplan_ids.mapped(
                "procedure_request_ids"
            ):
                procedure = request.procedure_ids
                self.assertEqual(len(procedure.sale_agent_ids), 1)
                self.assertEqual(len(procedure.invoice_agent_ids), 1)
                procedure.performer_id = self.practitioner_01
                procedure.commission_agent_id = self.practitioner_01
                procedure.check_commission()
                self.assertEqual(len(procedure.sale_agent_ids), 1)
                self.assertEqual(len(procedure.invoice_agent_ids), 3)

    def test_preinvoice_no_invoice(self):
        method = self.browse_ref(
            "cb_medical_careplan_sale.no_invoice_preinvoice"
        )
        self.plan_definition2.third_party_bill = False
        self.plan_definition.is_billable = True
        self.agreement.invoice_group_method_id = method
        self.agreement_line3.coverage_percentage = 100
        self.company.sale_merge_draft_invoice = True
        sale_orders = self.env["sale.order"]
        for i in range(1, 10):
            encounter, careplan, group = self.create_careplan_and_group(
                self.agreement_line3
            )
            self.assertTrue(group.procedure_request_ids)
            self.assertTrue(
                group.is_sellable_insurance or group.is_sellable_private
            )
            self.assertFalse(group.third_party_bill)
            self.env["wizard.medical.encounter.close"].create(
                {
                    "encounter_id": encounter.id,
                    "pos_session_id": self.session.id,
                }
            ).run()
            self.assertTrue(encounter.sale_order_ids)
            sale_order = encounter.sale_order_ids
            self.assertFalse(sale_order.third_party_order)
            for line in sale_order.order_line:
                self.assertFalse(line.agents)
            sale_orders |= sale_order
        self.session.action_pos_session_close()
        self.assertTrue(self.session.request_group_ids)
        preinvoice_obj = self.env["sale.preinvoice.group"]
        self.assertFalse(
            preinvoice_obj.search([("agreement_id", "=", self.agreement.id)])
        )
        self.env["wizard.sale.preinvoice.group"].create(
            {
                "company_ids": [(6, 0, self.company.ids)],
                "payor_ids": [(6, 0, self.payor.ids)],
            }
        ).run()
        self.assertFalse(
            preinvoice_obj.search([("agreement_id", "=", self.agreement.id)])
        )
        for encounter in self.session.encounter_ids:
            encounter_aux = self.env["medical.encounter"].browse(
                self.session.open_validation_encounter(
                    encounter.internal_identifier
                )["res_id"]
            )
            with self.assertRaises(ValidationError):
                encounter_aux.admin_validate()
            encounter.toggle_is_preinvoiced()
            encounter_aux.admin_validate()
            self.assertTrue(
                encounter.sale_order_ids.filtered(
                    lambda r: r.preinvoice_status == "to preinvoice"
                    and any(
                        line.invoice_group_method_id == method
                        for line in r.order_line
                    )
                )
            )
        self.env["wizard.sale.preinvoice.group"].create(
            {
                "company_ids": [(6, 0, self.company.ids)],
                "payor_ids": [(6, 0, self.payor.ids)],
            }
        ).run()
        preinvoices = preinvoice_obj.search(
            [("agreement_id", "=", self.agreement.id), ("state", "=", "draft")]
        )
        self.assertTrue(preinvoices)
        for preinvoice in preinvoices:
            self.assertTrue(preinvoice.non_validated_line_ids)
            self.assertFalse(preinvoice.validated_line_ids)
            preinvoice.start()
            preinvoice.close_sorting()
            self.assertTrue(preinvoice.non_validated_line_ids)
            preinvoice.close()
            self.assertFalse(preinvoice.non_validated_line_ids)
        preinvoices = preinvoice_obj.search(
            [("agreement_id", "=", self.agreement.id), ("state", "=", "draft")]
        )
        self.assertFalse(preinvoices)
        self.env["wizard.sale.preinvoice.group"].create(
            {
                "company_ids": [(6, 0, self.company.ids)],
                "payor_ids": [(6, 0, self.payor.ids)],
            }
        ).run()
        preinvoices = preinvoice_obj.search(
            [("agreement_id", "=", self.agreement.id), ("state", "=", "draft")]
        )
        self.assertTrue(preinvoices)
        invoice_obj = self.env["account.invoice"]
        self.assertFalse(
            invoice_obj.search([("partner_id", "=", self.payor.id)])
        )
        for preinvoice in preinvoices:
            self.assertFalse(preinvoice.validated_line_ids)
            preinvoice.start()
            barcode = self.env["wizard.sale.preinvoice.group.barcode"].create(
                {"preinvoice_group_id": preinvoice.id}
            )
            for encounter in self.session.encounter_ids:
                barcode.on_barcode_scanned(encounter.internal_identifier)
                self.assertEqual(barcode.status_state, 0)
            preinvoice.close_sorting()
            preinvoice.close()
            self.assertFalse(preinvoice.invoice_id)
        invoices = invoice_obj.search(
            [("partner_id", "in", [self.payor.id, self.sub_payor.id])]
        )
        self.assertFalse(invoices)
