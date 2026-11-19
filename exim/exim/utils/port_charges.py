# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def get_port_charges(port, charge_type="Import", table="charges"):
	"""Service charges configured in Import Export Charges for a port.

	`table` is "charges" (Import Shipment) or "supplier_quotation_charges" (Supplier Quotation;
	falls back to "charges" when it has no rows for the port).
	Returns [{"charge_type": service_item, "item_name": ..., "amount": ...}].
	"""
	if not port:
		return []

	name = frappe.db.get_value("Import Export Charges", {"port": port, "type": charge_type}, "name")
	if not name:
		return []

	charges_doc = frappe.get_cached_doc("Import Export Charges", name)
	rows = [r for r in charges_doc.get(table) or [] if r.service]
	if not rows and table != "charges":
		rows = [r for r in charges_doc.get("charges") or [] if r.service]
	item_names = dict(
		frappe.get_all(
			"Item",
			filters={"name": ("in", [r.service for r in rows])},
			fields=["name", "item_name"],
			as_list=True,
		)
	) if rows else {}

	return [
		{
			"charge_type": r.service,
			"item_name": item_names.get(r.service) or r.service,
			"amount": flt(r.amount),
		}
		for r in rows
	]


@frappe.whitelist()
def get_import_port_charges(port):
	frappe.has_permission("Supplier Quotation", "read", throw=True)
	return get_port_charges(port, "Import", table="supplier_quotation_charges")
