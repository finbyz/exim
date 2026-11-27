# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_data():
	data = {
		# other documents link back through their own "export_shipment" field
		"fieldname": "export_shipment",
		# links held on the shipment itself (header field / container rows)
		"internal_links": {
			"Sales Order": "sales_order",
			"Sales Invoice": ["containers", "sales_invoice"],
		},
		"transactions": [{"label": _("Sales"), "items": ["Sales Order", "Sales Invoice"]}],
	}
	# Container Loading Sheet is planned; show it once the doctype exists
	if frappe.db.exists("DocType", "Container Loading Sheet"):
		data["transactions"].append({"label": _("Logistics"), "items": ["Container Loading Sheet"]})
	return data
