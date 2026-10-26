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
	ensure_purchase_order_import_shipment_custom_field()
	sync_import_shipment_from_po(doc)


def update_import_shipment_on_submit(doc, method=None):
	"""
	When a Purchase Invoice is submitted:
	1. Set purchase_invoice or authorized_purchase_invoice on linked Import Shipment.
	2. For each service item linked to an Import Shipment, update or add charge in charges table.
	"""
	shipment_name = doc.get("import_shipment")
	if not shipment_name:
		for item in doc.get("items", []):
			if item.get("import_shipment"):
				shipment_name = item.import_shipment
				break

	if shipment_name and frappe.db.exists("Import Shipment", shipment_name):
		is_authorized = (
			(doc.get("authority") and str(doc.get("authority")).strip().lower() == "authorized")
			or bool(doc.get("unauthorized_purchase_invoice"))
		)
		target_col = "authorized_purchase_invoice" if is_authorized else "purchase_invoice"
		shipment_updates = {}
		if frappe.db.has_column("Import Shipment", target_col):
			shipment_updates[target_col] = doc.name

		passing_amt = flt(doc.get("total_discount_amount"))
		if passing_amt > 0 and frappe.db.has_column("Import Shipment", "passing_amount"):
			shipment_updates["passing_amount"] = passing_amt

		if shipment_updates:
			frappe.db.set_value(
				"Import Shipment",
				shipment_name,
				shipment_updates,
			)

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
	1. Revert purchase_invoice or authorized_purchase_invoice on linked Import Shipment.
	2. Revert actual amount on linked Import Shipment charges for service items.
	"""
	shipment_name = doc.get("import_shipment")
	if not shipment_name:
		for item in doc.get("items", []):
			if item.get("import_shipment"):
				shipment_name = item.import_shipment
				break

	if shipment_name and frappe.db.exists("Import Shipment", shipment_name):
		fields_to_check = []
		if frappe.db.has_column("Import Shipment", "purchase_invoice"):
			fields_to_check.append("purchase_invoice")
		if frappe.db.has_column("Import Shipment", "authorized_purchase_invoice"):
			fields_to_check.append("authorized_purchase_invoice")

		if fields_to_check:
			shipment_data = frappe.db.get_value(
				"Import Shipment",
				shipment_name,
				fields_to_check,
				as_dict=True,
			)
			if shipment_data:
				update_fields = {}
				if shipment_data.get("purchase_invoice") == doc.name:
					update_fields["purchase_invoice"] = None
				if shipment_data.get("authorized_purchase_invoice") == doc.name:
					update_fields["authorized_purchase_invoice"] = None
				if frappe.db.has_column("Import Shipment", "passing_amount"):
					update_fields["passing_amount"] = 0.0
				if update_fields:
					frappe.db.set_value("Import Shipment", shipment_name, update_fields)

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
