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
	"Lead": "public/js/doctype_js/lead.js",
	"Payment Entry": "public/js/doctype_js/payment_entry.js",

}
# fixtures = ["Custom Field"]
# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
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

doc_events = {
	"Sales Invoice": {
		"on_update": "exim.exim.doc_events.sales_invoice.cal_total",
		
	}
}

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

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "exim.event.get_events"
# }
# fixtures = ["Custom Field"]

# override_whitelisted_methods = {
# 	"frappe.utils.print_format.download_pdf": "exim.print_format.download_pdf",
# }

doc_events = {
	"Sales Invoice": {
		"on_submit": "exim.api.si_on_submit",
		"on_cancel": "exim.api.si_on_cancel",
		"before_save": "exim.api.si_before_save",
		"validate": "exim.api.si_validate"
	},
	"Purchase Invoice": {
		"on_submit": "exim.api.pi_on_submit",
		"on_cancel": "exim.api.pi_on_cancel", 
	},
	("Sales Invoice", "Purchase Invoice", "Payment Request", "Payment Entry", "Journal Entry", "Material Request", "Purchase Order", "Work Order", "Production Plan", "Stock Entry", "Quotation", "Sales Order", "Delivery Note", "Purchase Receipt", "Packing Slip"): {
		"before_naming": "exim.api.docs_before_naming",
	}
}
