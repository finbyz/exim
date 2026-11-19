# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "exim"
app_title = "Exim"
app_publisher = "FinByz Tech Pvt Ltd"
app_description = "custom app for exim module"
app_icon = "fa fa-ship"
app_color = "#61b590"
app_email = "info@finbyz.com"
app_license = "GPL 3.0"
app_version = "3.1.0"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/exim/css/exim.css"
# app_include_js = "/assets/exim/js/exim.js"
app_include_js = ["/assets/exim/js/serial_batch_container.js"]

# include js, css files in header of web template
# web_include_css = "/assets/exim/css/exim.css"
# web_include_js = "/assets/exim/js/exim.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

doctype_js = {
    "Sales Order": "public/js/doctype_js/sales_order.js",
    "Sales Invoice": "public/js/doctype_js/sales_invoice.js",
    "Delivery Note": "public/js/doctype_js/delivery_note.js",
    "Purchase Receipt": "public/js/doctype_js/purchase_receipt.js",
    "Purchase Invoice": "public/js/doctype_js/purchase_invoice.js",
    "Purchase Order": "public/js/doctype_js/purchase_order.js",
    "Supplier Quotation": "public/js/doctype_js/supplier_quotation.js",
    "Lead": "public/js/doctype_js/lead.js",
    "Payment Entry": "public/js/doctype_js/payment_entry.js",
    "Customize Form": "public/js/doctype_js/customize_form.js",
}
# after_migrate = ["exim.exim.doc_events.update_field_order.after_migrate"]

# fixtures = ["Custom Field"]
# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "exim.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "exim.install.before_install"
# after_install = "exim.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "exim.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events


# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"exim.tasks.all"
# 	],
# 	"daily": [
# 		"exim.tasks.daily"
# 	],
# 	"hourly": [
# 		"exim.tasks.hourly"
# 	],
# 	"weekly": [
# 		"exim.tasks.weekly"
# 	]
# 	"monthly": [
# 		"exim.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "exim.install.before_tests"

# override_doctype_class = {
# }

# payment term override
# nosemgrep: frappe-monkey-patching-not-allowed
# Reason: get_due_date is a module-level function with no Frappe hook/override
# support. Subclassing AccountsController is not viable because the function is
# called directly (not via self). Tracked in issue #<N> for upstream fix.
try:
    from erpnext.controllers import accounts_controller

    from exim.exim.monkey_patch.accounts_controller import get_due_date

    accounts_controller.get_due_date = get_due_date
except ImportError:
    pass


# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "exim.event.get_events"
# }
# fixtures = ["Custom Field"]

accounting_dimension_doctypes = ["Drawback Details", "Rodtep Details"]

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "in", ["Exim"]]]},
    {"dt": "Property Setter", "filters": [["module", "in", ["Exim"]]]},
    {"dt": "Item", "filters": [["item_code", "in", ["Custom Duty"]]]},
]
override_whitelisted_methods = {
    "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice": "exim.exim.utils.purchase_invoice.make_purchase_invoice",
    # Container No in the Serial / Batch selector (CSV upload and dialog table)
    "erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle.upload_csv_file": "exim.exim.utils.serial_batch_container.upload_csv_file",
    "erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle.add_serial_batch_ledgers": "exim.exim.utils.serial_batch_container.add_serial_batch_ledgers",
    "erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle.get_serial_batch_ledgers": "exim.exim.utils.serial_batch_container.get_serial_batch_ledgers",
    "frappe.utils.print_format.download_pdf": "exim.exim.utils.shipment_attachments.custom_download_pdf",
}

doc_events = {
    "Print Format": {
        # formats showing shipment attachments always use the "Attachments" PDF generator
        "validate": "exim.exim.utils.shipment_attachments.set_attachments_pdf_generator",
    },
    "Serial and Batch Bundle": {
        "validate": "exim.exim.utils.serial_batch_container.set_entry_containers",
    },
    "Sales Invoice": {
        "before_save": "exim.exim.doc_events.sales_invoice.before_save",
        "validate": "exim.exim.doc_events.sales_invoice.validate",
        "on_submit": "exim.exim.doc_events.sales_invoice.on_submit",
        "on_cancel": "exim.exim.doc_events.sales_invoice.on_cancel",
    },
    "Purchase Invoice": {
        "validate": "exim.exim.utils.purchase_invoice.validate_purchase_invoice",
        "on_update": "exim.exim.utils.purchase_invoice.update_import_shipment_on_update",
        "on_update_after_submit": "exim.exim.utils.purchase_invoice.update_import_shipment_on_update",
        "on_submit": [
            "exim.exim.doc_events.purchase_invoice.pi_on_submit",
            "exim.exim.utils.purchase_invoice.update_import_shipment_on_submit",
        ],
        "on_cancel": [
            "exim.exim.doc_events.purchase_invoice.pi_on_cancel",
            "exim.exim.utils.purchase_invoice.update_import_shipment_on_cancel",
        ],
    },
    "Bill of Entry": {
        "on_update": "exim.exim.utils.bill_of_entry.update_import_shipment_from_boe",
        "on_submit": "exim.exim.utils.bill_of_entry.update_import_shipment_from_boe",
        "on_cancel": "exim.exim.utils.bill_of_entry.update_import_shipment_from_boe_on_cancel",
    },
    (
        "Purchase Invoice",
        "Payment Request",
        "Payment Entry",
        "Journal Entry",
        "Material Request",
        "Purchase Order",
        "Work Order",
        "Production Plan",
        "Stock Entry",
        "Quotation",
        "Sales Order",
        "Delivery Note",
        "Purchase Receipt",
        "Packing Slip",
    ): {
        # "before_naming": "exim.api.docs_before_naming",
    },
    "Rodtep Claim": {
        "on_submit": "exim.exim.doctype.rodtep_claim.rodtep_claim.create_jv_on_submit"
    },
    "Duty DrawBack Claim": {
        "on_submit": "exim.exim.doctype.duty_drawback_claim.duty_drawback_claim.create_jv_on_submit"
    },
    "IGST Refund Claim": {
        "on_submit": "exim.exim.doctype.igst_refund_claim.igst_refund_claim.create_jv_on_submit"
    },
    "Payment Entry": {
        "on_submit": "exim.api.pe_on_submit",
        "before_cancel": "exim.api.pe_on_cancel",
    },
    ("Delivery Note", "Sales Invoice"): {
        "validate": "exim.exim.doc_events.igst_calculation.cal_igst"
    },
}

# Print formats: {{ get_attachment_files(doc) }} -> the shipment's attached files (preview)
jinja = {
    "methods": [
        "exim.exim.utils.shipment_attachments.get_attachment_files",
        "exim.exim.utils.shipment_attachments.get_attachment_pages",
    ],
}

# Print Format with PDF Generator = "Attachments": PDF made of the real attached files
pdf_generator = ["exim.exim.utils.shipment_attachments.attachments_pdf_generator"]
