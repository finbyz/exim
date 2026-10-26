# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def get_boe_details_for_shipment(
	shipment_doc=None,
	shipment_name=None,
	authorized_purchase_invoice=None,
	be_no=None,
):
	"""
	Find Bill of Entry records related to an Import Shipment (via authorized_purchase_invoice,
	purchase_invoice, or be_no) and calculate:
	- duty_basic <= total_customs_duty
	- cess_and_gst <= total_taxes
	"""
	if not frappe.db.table_exists("Bill of Entry"):
		return {"has_boe": False, "total_customs_duty": 0.0, "total_taxes": 0.0}

	if shipment_name and not shipment_doc:
		if frappe.db.exists("Import Shipment", shipment_name):
			shipment_doc = frappe.get_doc("Import Shipment", shipment_name)

	auth_pi = (
		authorized_purchase_invoice
		or (shipment_doc.get("authorized_purchase_invoice") if shipment_doc else None)
	)
	unauth_pi = shipment_doc.get("purchase_invoice") if shipment_doc else None
	be_number = be_no or (shipment_doc.get("be_no") if shipment_doc else None)

	# 1. Collect distinct BOE names related to the Purchase Invoice(s)
	boe_names = set()
	pis_to_search = [p for p in [auth_pi, unauth_pi] if p]

	if pis_to_search and frappe.db.table_exists("Bill of Entry Item"):
		found_boe_names = frappe.get_all(
			"Bill of Entry Item",
			filters={"purchase_invoice": ["in", pis_to_search], "docstatus": ["<", 2]},
			pluck="parent",
			distinct=True,
		)
		boe_names.update(found_boe_names)

	# 2. Fallback search via be_no if no BOEs found via Purchase Invoice
	if not boe_names and be_number:
		found_by_no = frappe.get_all(
			"Bill of Entry",
			filters={"bill_of_entry_no": be_number, "docstatus": ["<", 2]},
			pluck="name",
		)
		if found_by_no:
			boe_names.update(found_by_no)
		elif frappe.db.exists("Bill of Entry", be_number):
			boe_names.add(be_number)

	if not boe_names:
		return {
			"has_boe": False,
			"total_customs_duty": 0.0,
			"total_taxes": 0.0,
			"bill_of_entry_no": None,
			"bill_of_entry_date": None,
			"boe_names": [],
		}

	# 3. Calculate total_customs_duty and total_taxes from active BOEs
	total_customs_duty = 0.0
	total_taxes = 0.0
	latest_be_no = None
	latest_be_date = None

	boe_records = frappe.get_all(
		"Bill of Entry",
		filters={"name": ["in", list(boe_names)], "docstatus": ["<", 2]},
		fields=[
			"name",
			"bill_of_entry_no",
			"bill_of_entry_date",
			"total_customs_duty",
			"total_taxes",
			"docstatus",
		],
		order_by="docstatus desc, creation desc",
	)

	for boe_info in boe_records:
		boe_name = boe_info.name
		if not latest_be_no and boe_info.bill_of_entry_no:
			latest_be_no = boe_info.bill_of_entry_no
		if not latest_be_date and boe_info.bill_of_entry_date:
			latest_be_date = boe_info.bill_of_entry_date

		# Check if items are mixed or all for this invoice
		boe_items = frappe.get_all(
			"Bill of Entry Item",
			filters={"parent": boe_name},
			fields=[
				"purchase_invoice",
				"customs_duty",
				"igst_amount",
				"cgst_amount",
				"sgst_amount",
				"cess_amount",
				"cess_non_advol_amount",
			],
		)

		has_other_pis = False
		if pis_to_search and boe_items:
			for row in boe_items:
				if row.purchase_invoice and row.purchase_invoice not in pis_to_search:
					has_other_pis = True
					break

		if not has_other_pis:
			# Entire BOE belongs to this shipment's invoice
			total_customs_duty += flt(boe_info.total_customs_duty)
			total_taxes += flt(boe_info.total_taxes)
		else:
			# Mixed BOE: sum item-level duty and taxes for this invoice
			matched_duty = 0.0
			matched_taxes = 0.0
			for row in boe_items:
				if row.purchase_invoice in pis_to_search:
					matched_duty += flt(row.customs_duty)
					matched_taxes += (
						flt(row.igst_amount)
						+ flt(row.cgst_amount)
						+ flt(row.sgst_amount)
						+ flt(row.cess_amount)
						+ flt(row.cess_non_advol_amount)
					)
			# Fallback to header if item-level taxes not broken down
			total_customs_duty += matched_duty or flt(boe_info.total_customs_duty)
			total_taxes += matched_taxes or flt(boe_info.total_taxes)

	return {
		"has_boe": True,
		"total_customs_duty": flt(total_customs_duty, 2),
		"total_taxes": flt(total_taxes, 2),
		"bill_of_entry_no": latest_be_no or (boe_records[0].name if boe_records else None),
		"bill_of_entry_date": latest_be_date,
		"boe_names": [b.name for b in boe_records],
	}


@frappe.whitelist()
def get_bill_of_entry_details(shipment_name=None, authorized_purchase_invoice=None, be_no=None):
	"""
	Whitelisted endpoint for client-side Desk UI.
	Optionally persists duty_basic and cess_and_gst to DB if shipment_name is provided.
	"""
	data = get_boe_details_for_shipment(
		shipment_name=shipment_name,
		authorized_purchase_invoice=authorized_purchase_invoice,
		be_no=be_no,
	)

	if shipment_name and frappe.db.exists("Import Shipment", shipment_name) and data.get("has_boe"):
		update_values = {
			"duty_basic": data.get("total_customs_duty", 0.0),
			"cess_and_gst": data.get("total_taxes", 0.0),
		}
		curr_be_no = frappe.db.get_value("Import Shipment", shipment_name, "be_no")
		curr_be_date = frappe.db.get_value("Import Shipment", shipment_name, "be_date")

		if not curr_be_no and data.get("bill_of_entry_no"):
			update_values["be_no"] = data.get("bill_of_entry_no")
		if not curr_be_date and data.get("bill_of_entry_date"):
			update_values["be_date"] = data.get("bill_of_entry_date")

		frappe.db.set_value("Import Shipment", shipment_name, update_values)

	return data


def get_linked_shipment_names_for_boe(boe_doc):
	"""Find all Import Shipment records connected to a Bill of Entry."""
	shipment_names = set()

	# 1. Via purchase_invoice in BOE items
	pi_names = [
		row.purchase_invoice
		for row in boe_doc.get("items", [])
		if getattr(row, "purchase_invoice", None)
	]

	if pi_names:
		# Search Import Shipment by authorized_purchase_invoice
		found_auth = frappe.get_all(
			"Import Shipment",
			filters={"authorized_purchase_invoice": ["in", pi_names]},
			pluck="name",
		)
		shipment_names.update(found_auth)

		# Search Import Shipment by purchase_invoice
		found_unauth = frappe.get_all(
			"Import Shipment",
			filters={"purchase_invoice": ["in", pi_names]},
			pluck="name",
		)
		shipment_names.update(found_unauth)

		# Check import_shipment link on Purchase Invoices
		for pi_name in pi_names:
			if frappe.db.has_column("Purchase Invoice", "import_shipment"):
				shp = frappe.db.get_value("Purchase Invoice", pi_name, "import_shipment")
				if shp and frappe.db.exists("Import Shipment", shp):
					shipment_names.add(shp)

	# 2. Via be_no match on Import Shipment
	be_nos = [b for b in [boe_doc.get("bill_of_entry_no"), boe_doc.get("name")] if b]
	if be_nos:
		found_be = frappe.get_all(
			"Import Shipment",
			filters={"be_no": ["in", be_nos]},
			pluck="name",
		)
		shipment_names.update(found_be)

	return shipment_names


def sync_shipment_boe_taxes(shipment_name):
	"""Sync duty_basic and cess_and_gst from related BOE for a specific Import Shipment."""
	if not shipment_name or not frappe.db.exists("Import Shipment", shipment_name):
		return

	boe_data = get_boe_details_for_shipment(shipment_name=shipment_name)
	update_values = {
		"duty_basic": boe_data.get("total_customs_duty", 0.0),
		"cess_and_gst": boe_data.get("total_taxes", 0.0),
	}

	curr_be_no = frappe.db.get_value("Import Shipment", shipment_name, "be_no")
	curr_be_date = frappe.db.get_value("Import Shipment", shipment_name, "be_date")

	if not curr_be_no and boe_data.get("bill_of_entry_no"):
		update_values["be_no"] = boe_data.get("bill_of_entry_no")
	if not curr_be_date and boe_data.get("bill_of_entry_date"):
		update_values["be_date"] = boe_data.get("bill_of_entry_date")

	if frappe.db.has_column("Import Shipment", "passing_amount"):
		curr_passing = frappe.db.get_value("Import Shipment", shipment_name, "passing_amount")
		if not flt(curr_passing):
			disc_amt = 0.0
			try:
				# pyrefly: ignore [missing-import]
				from data_sync.data_sync.doc_events.import_shipment import sync_shipment_passing_from_pi
				disc_amt = sync_shipment_passing_from_pi(shipment_name)
			except ImportError:
				auth_pi, unauth_pi = frappe.db.get_value(
					"Import Shipment", shipment_name, ["authorized_purchase_invoice", "purchase_invoice"]
				)
				for pi in [auth_pi, unauth_pi]:
					if pi and frappe.db.has_column("Purchase Invoice", "total_discount_amount"):
						disc_amt = flt(frappe.db.get_value("Purchase Invoice", pi, "total_discount_amount"))
						if disc_amt:
							break
			if disc_amt > 0:
				update_values["passing_amount"] = disc_amt

	frappe.db.set_value("Import Shipment", shipment_name, update_values)


def update_import_shipment_from_boe(doc, method=None):
	"""
	Hook on Bill of Entry on_update and on_submit:
	Updates duty_basic (total_customs_duty) and cess_and_gst (total_taxes)
	on all linked Import Shipment records.
	"""
	shipment_names = get_linked_shipment_names_for_boe(doc)
	for shipment_name in shipment_names:
		sync_shipment_boe_taxes(shipment_name)


def update_import_shipment_from_boe_on_cancel(doc, method=None):
	"""
	Hook on Bill of Entry on_cancel:
	Re-evaluates and updates duty_basic and cess_and_gst excluding the cancelled BOE.
	"""
	shipment_names = get_linked_shipment_names_for_boe(doc)
	for shipment_name in shipment_names:
		sync_shipment_boe_taxes(shipment_name)
