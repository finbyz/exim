import frappe
from frappe.model.document import Document
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    make_dimension_in_accounting_doctypes,
)

class EximSettings(Document):
    def before_save(self):
        old_value = frappe.db.get_single_value(
            "Exim Settings",
            "manage_rodtep_claim_and_duty_drawback_claim"
        )

        # OFF → ON
        if self.manage_rodtep_claim_and_duty_drawback_claim and not old_value:
            self.create_dimensions()

        # ON → OFF
        if not self.manage_rodtep_claim_and_duty_drawback_claim and old_value:
            self.remove_dimensions()

    def get_exim_doctypes(self):
        return frappe.get_hooks(
            "accounting_dimension_doctypes",
            app_name="exim",
        ) or []

    def create_dimensions(self):
        doctypes = self.get_exim_doctypes()
        if not doctypes:
            return

        dimensions = frappe.get_all("Accounting Dimension", pluck="name")

        for dimension in dimensions:
            doc = frappe.get_doc("Accounting Dimension", dimension)
            make_dimension_in_accounting_doctypes(doc, doctypes)

    def remove_dimensions(self):
        doctypes = self.get_exim_doctypes()
        if not doctypes:
            return

        dimensions = frappe.get_all(
            "Accounting Dimension",
            fields=["name", "document_type"]
        )

        for d in dimensions:
            fieldname = frappe.scrub(d.name)

            for doctype in doctypes:
                custom_field_name = f"{doctype}-{fieldname}"

                if frappe.db.exists("Custom Field", custom_field_name):
                    frappe.delete_doc(
                        "Custom Field",
                        custom_field_name,
                        force=1
                    )
