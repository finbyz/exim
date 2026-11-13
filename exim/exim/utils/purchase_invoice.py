# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from collections import defaultdict
import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form


def is_service_item(item_code, item_row=None):
	"""Check if an item is a service/non-stock item."""
	if item_row and hasattr(item_row, "is_stock_item") and item_row.is_stock_item is not None:
		return not item_row.is_stock_item
	return not frappe.db.get_value("Item", item_code, "is_stock_item")


def get_shipment_items_map(doc):
	"""Group service items by target Import Shipment."""
	shipment_items = defaultdict(list)

	for item in doc.get("items", []):
		if not item.item_code:
			continue

		shipment_name = getattr(item, "import_shipment", None) or getattr(doc, "import_shipment", None)
		if not shipment_name:
			continue

		if is_service_item(item.item_code, item):
			shipment_items[shipment_name].append(item)

	return shipment_items


def ensure_import_shipment_pi_fields():
	"""Ensure purchase_invoice and authorized_purchase_invoice columns exist on Import Shipment."""
	pass


def ensure_pi_import_shipment_allow_on_submit():
	"""Ensure import_shipment on Purchase Invoice and Purchase Invoice Item have allow_on_submit=1."""
	try:
		changed = False
		for cf_name in ("Purchase Invoice Item-import_shipment", "Purchase Invoice-import_shipment"):
			if frappe.db.exists("Custom Field", cf_name):
				if not frappe.db.get_value("Custom Field", cf_name, "allow_on_submit"):
					frappe.db.set_value("Custom Field", cf_name, "allow_on_submit", 1, update_modified=False)
					changed = True
		if changed:
			frappe.clear_cache(doctype="Purchase Invoice")
			frappe.clear_cache(doctype="Purchase Invoice Item")
	except Exception:
		pass


def ensure_purchase_order_import_shipment_custom_field():
	"""Ensure import_shipment custom field exists on Purchase Order."""
	try:
		if not frappe.db.exists("Custom Field", "Purchase Order-import_shipment"):
			from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

			create_custom_fields(
				{
					"Purchase Order": [
						{
							"fieldname": "import_shipment",
							"fieldtype": "Link",
							"label": "Import Shipment",
							"options": "Import Shipment",
							"insert_after": "supplier",
							"in_standard_filter": 1,
							"module": "Exim",
						}
					]
				},
				update=True,
			)
	except Exception:
		pass


def get_import_shipment_for_purchase_order(po_name):
	"""Get Import Shipment linked to a Purchase Order."""
	if not po_name:
		return None

	if frappe.db.has_column("Purchase Order", "import_shipment"):
		shipment = frappe.db.get_value("Purchase Order", po_name, "import_shipment")
		if shipment:
			return shipment

	shipment = frappe.db.get_value(
		"Import Shipment Item",
		{"purchase_order": po_name},
		"parent",
		order_by="creation desc",
	)
	if shipment:
		return shipment

	return None


def get_import_shipment_for_purchase_order_item(po_item_name):
	"""Get Import Shipment linked to a Purchase Order Item."""
	if not po_item_name:
		return None

	return frappe.db.get_value(
		"Import Shipment Item",
		{"purchase_order_item": po_item_name},
		"parent",
		order_by="creation desc",
	)


def sync_import_shipment_from_po(doc):
	"""Transfer Import Shipment from Purchase Order / Items to Purchase Invoice."""
	if not doc.get("import_shipment"):
		for item in doc.get("items", []):
			shipment = None
			if item.get("po_detail"):
				shipment = get_import_shipment_for_purchase_order_item(item.po_detail)
			if not shipment and item.get("purchase_order"):
				shipment = get_import_shipment_for_purchase_order(item.purchase_order)
			if shipment:
				doc.import_shipment = shipment
				break

	if doc.get("import_shipment"):
		for item in doc.get("items", []):
			if not item.get("import_shipment"):
				item.import_shipment = doc.import_shipment


@frappe.whitelist()
def get_po_import_shipment(purchase_order):
	"""Whitelisted helper for client-side to fetch Import Shipment from PO."""
	return get_import_shipment_for_purchase_order(purchase_order)


@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, args=None):
	"""Override of erpnext make_purchase_invoice to transfer Import Shipment."""
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_invoice as erpnext_make_purchase_invoice,
	)

	doc = erpnext_make_purchase_invoice(source_name, target_doc=target_doc, args=args)
	sync_import_shipment_from_po(doc)
	return doc


def validate_purchase_invoice(doc, method=None):
	"""Sync import_shipment from linked Purchase Order."""
	ensure_pi_import_shipment_allow_on_submit()
	ensure_purchase_order_import_shipment_custom_field()
	sync_import_shipment_from_po(doc)


def is_commercial_purchase_invoice(doc):
	"""
	Returns True if this Purchase Invoice is for commercial goods,
	rather than only freight/service expenses.
	"""
	for item in doc.get("items", []):
		if item.item_code and not is_service_item(item.item_code, item):
			return True

	if doc.get("authority") or doc.get("unauthorized_purchase_invoice"):
		return True

	return False


def sync_commercial_pi_to_shipment(doc, shipment_name=None):
	"""
	Sync commercial values from Purchase Invoice to linked Import Shipment:
	- invoice_value = doc.grand_total
	- exchange_rate = doc.conversion_rate
	- invoice_value_inr = doc.base_grand_total
	- invoice_no = doc.bill_no or doc.name
	- invoice_date = doc.bill_date or doc.posting_date
	- purchase_invoice / authorized_purchase_invoice = doc.name
	- cif_value = invoice_value_inr + insurance
	"""
	target_shipment = shipment_name or doc.get("import_shipment")
	if not target_shipment:
		for item in doc.get("items", []):
			if item.get("import_shipment"):
				target_shipment = item.import_shipment
				break

	if not target_shipment or not frappe.db.exists("Import Shipment", target_shipment):
		return

	if not is_commercial_purchase_invoice(doc):
		return

	# Revert any other shipments previously linked to this Purchase Invoice
	other_linked_shipments = frappe.get_all(
		"Import Shipment",
		filters=[
			["name", "!=", target_shipment],
			["purchase_invoice", "=", doc.name],
		],
		pluck="name",
	) + frappe.get_all(
		"Import Shipment",
		filters=[
			["name", "!=", target_shipment],
			["authorized_purchase_invoice", "=", doc.name],
		],
		pluck="name",
	)
	for old_name in set(other_linked_shipments):
		revert_commercial_pi_from_shipment(doc, old_name)

	is_authorized = (
		(doc.get("authority") and str(doc.get("authority")).strip().lower() == "authorized")
		or bool(doc.get("unauthorized_purchase_invoice"))
	)
	target_col = "authorized_purchase_invoice" if is_authorized else "purchase_invoice"

	inv_value = flt(doc.grand_total)
	conv_rate = flt(doc.conversion_rate) if flt(doc.conversion_rate) > 0 else 1.0
	inv_value_inr = flt(doc.base_grand_total) if flt(doc.base_grand_total) > 0 else (inv_value * conv_rate)
	inv_no = doc.bill_no or doc.name
	inv_date = doc.bill_date or doc.posting_date

	update_values = {}
	if frappe.db.has_column("Import Shipment", target_col):
		update_values[target_col] = doc.name
	if frappe.db.has_column("Import Shipment", "invoice_value"):
		update_values["invoice_value"] = inv_value
	if frappe.db.has_column("Import Shipment", "exchange_rate"):
		update_values["exchange_rate"] = conv_rate
	if frappe.db.has_column("Import Shipment", "invoice_value_inr"):
		update_values["invoice_value_inr"] = inv_value_inr
	if frappe.db.has_column("Import Shipment", "invoice_no"):
		update_values["invoice_no"] = inv_no
	if frappe.db.has_column("Import Shipment", "invoice_date") and inv_date:
		update_values["invoice_date"] = inv_date
	if doc.currency and frappe.db.has_column("Import Shipment", "currency"):
		update_values["currency"] = doc.currency

	if frappe.db.has_column("Import Shipment", "cif_value"):
		curr_ins = flt(frappe.db.get_value("Import Shipment", target_shipment, "insurance"))
		update_values["cif_value"] = inv_value_inr + curr_ins

	passing_amt = flt(doc.get("total_discount_amount"))
	if passing_amt > 0 and frappe.db.has_column("Import Shipment", "passing_amount"):
		update_values["passing_amount"] = passing_amt

	if update_values:
		frappe.db.set_value("Import Shipment", target_shipment, update_values)


def revert_commercial_pi_from_shipment(doc, shipment_name):
	"""
	Revert commercial values on Import Shipment if this Purchase Invoice was unlinked or cancelled.
	"""
	if not shipment_name or not frappe.db.exists("Import Shipment", shipment_name):
		return

	shp = frappe.db.get_value(
		"Import Shipment",
		shipment_name,
		["purchase_invoice", "authorized_purchase_invoice", "insurance"],
		as_dict=True,
	)
	if not shp:
		return

	is_linked = (shp.purchase_invoice == doc.name or shp.authorized_purchase_invoice == doc.name)
	if not is_linked:
		return

	other_pi = frappe.db.get_value(
		"Purchase Invoice",
		{"import_shipment": shipment_name, "name": ["!=", doc.name], "docstatus": ["!=", 2]},
		["name", "grand_total", "base_grand_total", "conversion_rate", "bill_no", "bill_date", "currency", "authority", "unauthorized_purchase_invoice"],
		as_dict=True,
		order_by="docstatus desc, creation desc",
	)

	update_values = {}
	if other_pi:
		is_auth = (other_pi.authority and str(other_pi.authority).strip().lower() == "authorized") or bool(other_pi.unauthorized_purchase_invoice)
		target_col = "authorized_purchase_invoice" if is_auth else "purchase_invoice"
		other_col = "purchase_invoice" if is_auth else "authorized_purchase_invoice"

		inv_val = flt(other_pi.grand_total)
		conv = flt(other_pi.conversion_rate) or 1.0
		inv_val_inr = flt(other_pi.base_grand_total) or (inv_val * conv)

		update_values[target_col] = other_pi.name
		update_values[other_col] = None
		update_values["invoice_value"] = inv_val
		update_values["exchange_rate"] = conv
		update_values["invoice_value_inr"] = inv_val_inr
		update_values["invoice_no"] = other_pi.bill_no or other_pi.name
		if other_pi.bill_date:
			update_values["invoice_date"] = other_pi.bill_date
		if other_pi.currency:
			update_values["currency"] = other_pi.currency
		update_values["cif_value"] = inv_val_inr + flt(shp.insurance)
	else:
		update_values["purchase_invoice"] = None
		update_values["authorized_purchase_invoice"] = None
		update_values["invoice_value"] = 0.0
		update_values["invoice_value_inr"] = 0.0
		update_values["invoice_no"] = None
		update_values["invoice_date"] = None
		update_values["cif_value"] = flt(shp.insurance)

	frappe.db.set_value("Import Shipment", shipment_name, update_values)


def update_import_shipment_on_update(doc, method=None):
	"""
	Hook on Purchase Invoice on_update:
	Syncs commercial details to linked Import Shipment.
	"""
	doc_before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	if doc_before:
		old_shipment = doc_before.get("import_shipment")
		new_shipment = doc.get("import_shipment")
		if old_shipment and old_shipment != new_shipment:
			revert_commercial_pi_from_shipment(doc, old_shipment)

	if doc.get("import_shipment"):
		sync_commercial_pi_to_shipment(doc)


@frappe.whitelist()
def sync_pi_import_shipment_commercial(purchase_invoice, import_shipment=None):
	"""Whitelisted helper for client-side when import_shipment is selected on Purchase Invoice."""
	if not purchase_invoice or not frappe.db.exists("Purchase Invoice", purchase_invoice):
		return {"success": False}

	doc = frappe.get_doc("Purchase Invoice", purchase_invoice)
	target_shipment = import_shipment or doc.get("import_shipment")
	if target_shipment and frappe.db.exists("Import Shipment", target_shipment):
		old_shipment = doc.get("import_shipment")
		if old_shipment and old_shipment != target_shipment:
			revert_commercial_pi_from_shipment(doc, old_shipment)
		sync_commercial_pi_to_shipment(doc, shipment_name=target_shipment)
		return {"success": True}
	return {"success": False}


def update_import_shipment_on_submit(doc, method=None):
	"""
	When a Purchase Invoice is submitted:
	1. Set purchase_invoice or authorized_purchase_invoice on linked Import Shipment.
	2. Sync commercial invoice values (invoice_value, invoice_value_inr, exchange_rate, etc.).
	3. For each service item linked to an Import Shipment, update or add charge in charges table.
	"""
	sync_commercial_pi_to_shipment(doc)

	shipment_items_map = get_shipment_items_map(doc)
	if not shipment_items_map:
		return

	invoice_date = doc.bill_date or doc.posting_date

	for shipment_name, items in shipment_items_map.items():
		if not frappe.db.exists("Import Shipment", shipment_name):
			continue

		shipment_doc = frappe.get_doc("Import Shipment", shipment_name)

		for item in items:
			item_amount = flt(item.base_net_amount or item.net_amount or item.amount)
			matched_charge = None

			for charge in shipment_doc.get("charges", []):
				if charge.charge_type == item.item_code:
					matched_charge = charge
					break

			if matched_charge:
				matched_charge.actual_amount = flt(matched_charge.actual_amount) + item_amount
				matched_charge.invoice_no = doc.name
				matched_charge.invoice_date = invoice_date
				if not matched_charge.item_name:
					matched_charge.item_name = item.item_name
			else:
				shipment_doc.append(
					"charges",
					{
						"charge_type": item.item_code,
						"item_name": item.item_name,
						"amount": 0.0,
						"actual_amount": item_amount,
						"invoice_no": doc.name,
						"invoice_date": invoice_date,
						"remarks": f"Added from Purchase Invoice {doc.name}",
					},
				)

		shipment_doc.save(ignore_permissions=True)


def update_import_shipment_on_cancel(doc, method=None):
	"""
	When a Purchase Invoice is cancelled:
	1. Revert commercial values and purchase_invoice link on linked Import Shipment.
	2. Revert actual amount on linked Import Shipment charges for service items.
	"""
	shipment_name = doc.get("import_shipment")
	if not shipment_name:
		for item in doc.get("items", []):
			if item.get("import_shipment"):
				shipment_name = item.import_shipment
				break

	if shipment_name and frappe.db.exists("Import Shipment", shipment_name):
		revert_commercial_pi_from_shipment(doc, shipment_name)

	shipment_items_map = get_shipment_items_map(doc)
	if not shipment_items_map:
		return

	for shipment_name, items in shipment_items_map.items():
		if not frappe.db.exists("Import Shipment", shipment_name):
			continue

		shipment_doc = frappe.get_doc("Import Shipment", shipment_name)

		for item in items:
			item_amount = flt(item.base_net_amount or item.net_amount or item.amount)

			for charge in shipment_doc.get("charges", []):
				if charge.charge_type == item.item_code:
					charge.actual_amount = max(0.0, flt(charge.actual_amount) - item_amount)
					if charge.invoice_no == doc.name:
						charge.invoice_no = None
						charge.invoice_date = None

		shipment_doc.save(ignore_permissions=True)
