# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate
from erpnext.controllers.mapper import get_qty_already_mapped


class ImportShipment(Document):
	def before_insert(self):
		if not self.shipment_no and self.name and not self.name.startswith("new-"):
			self.shipment_no = self.name

	def validate(self):
		if not self.shipment_no and self.name and not self.name.startswith("new-"):
			self.shipment_no = self.name
		self.set_currency_and_company_defaults()
		self.validate_purchase_order_qty()
		self.calculate_week()
		self.calculate_item_totals()
		self.auto_fill_destination_port_charges()
		self.calculate_charge_totals()
		self.calculate_rates()
		self.calculate_commercial_totals()
		self.update_boe_details()

	def auto_fill_destination_port_charges(self):
		if not getattr(self, "destination_port", None):
			return

		has_charges = any(row.get("charge_type") for row in (self.get("charges") or []))
		if has_charges:
			return

		charges = get_charges_for_destination_port(self.destination_port)
		if not charges:
			return

		self.set("charges", [])
		for item in charges:
			self.append("charges", {
				"charge_type": item["charge_type"],
				"item_name": item["item_name"],
				"amount": item["amount"],
			})

	def on_update(self):
		if not self.shipment_no and self.name and not self.name.startswith("new-"):
			self.db_set("shipment_no", self.name, update_modified=False)
			self.shipment_no = self.name

	def set_currency_and_company_defaults(self):
		if not getattr(self, "company", None) or "get_user_default" in str(self.company):
			self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")

		company_currency = None
		if self.company:
			company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		if not company_currency:
			company_currency = frappe.db.get_single_value("Global Defaults", "default_currency") or "INR"

		if not getattr(self, "currency", None):
			self.currency = company_currency

		if not flt(self.exchange_rate) or flt(self.exchange_rate) <= 0:
			if self.currency == company_currency:
				self.exchange_rate = 1.0

		for item in self.get("items", []):
			item.currency = self.currency

	def validate_purchase_order_qty(self):
		shipment_qty_by_po_item = {}
		for item in self.get("items", []):
			if not item.purchase_order_item:
				continue
			shipment_qty_by_po_item[item.purchase_order_item] = (
				shipment_qty_by_po_item.get(item.purchase_order_item, 0.0) + flt(item.qty)
			)

		validated_po_items = set()
		for item in self.get("items", []):
			if not item.purchase_order_item or item.purchase_order_item in validated_po_items:
				continue

			po_item = frappe.db.get_value(
				"Purchase Order Item",
				item.purchase_order_item,
				["item_code", "qty", "parent"],
				as_dict=True,
			)
			if not po_item:
				continue

			po_qty = flt(po_item.get("qty") if isinstance(po_item, dict) else getattr(po_item, "qty", 0.0))
			po_item_code = po_item.get("item_code") if isinstance(po_item, dict) else getattr(po_item, "item_code", "")
			po_parent = po_item.get("parent") if isinstance(po_item, dict) else getattr(po_item, "parent", "")
			exclude_name = self.name if (self.name and not self.name.startswith("new-")) else None
			already_shipped = get_shipped_qty_for_po_item(item.purchase_order_item, exclude_shipment=exclude_name)

			total_shipment_qty = flt(shipment_qty_by_po_item.get(item.purchase_order_item, 0.0))
			remaining_qty = po_qty - already_shipped

			if total_shipment_qty > (remaining_qty + 0.0001):
				frappe.throw(
					_(
						"Row #{0}: Quantity {1} for Item {2} exceeds the available quantity in Purchase Order {3}.<br><br>"
						"• Purchase Order Total: {4}<br>"
						"• Already Shipped in other shipments: {5}<br>"
						"• Maximum Available to Ship: {6}"
					).format(
						item.idx,
						total_shipment_qty,
						frappe.bold(item.product or po_item_code),
						frappe.bold(item.purchase_order or po_parent),
						po_qty,
						already_shipped,
						max(0.0, remaining_qty),
					),
					title=_("Quantity Exceeds Purchase Order"),
				)

			validated_po_items.add(item.purchase_order_item)

	def calculate_rates(self):
		total_base_item_amount = flt(self.total_item_amount_inr)
		total_tentative_charges = flt(self.total_expenses)
		total_actual_charges = flt(self.total_actual_expenses)

		for item in self.get("items", []):
			qty = flt(item.qty)
			base_amount = flt(item.base_amount)

			if total_base_item_amount > 0 and qty > 0:
				item_ratio = base_amount / total_base_item_amount
				allocated_tentative = total_tentative_charges * item_ratio
				allocated_actual = total_actual_charges * item_ratio

				item.tentative_rate = (base_amount + allocated_tentative) / qty
				item.landed_rate = (base_amount + allocated_actual) / qty
			elif qty > 0:
				item.tentative_rate = flt(item.base_rate)
				item.landed_rate = flt(item.base_rate)
			else:
				item.tentative_rate = 0.0
				item.landed_rate = 0.0

	def calculate_week(self):
		if self.eta:
			try:
				eta_date = getdate(self.eta)
				self.week = eta_date.isocalendar()[1]
			except Exception:
				self.week = None

	def calculate_item_totals(self):
		total_boxes = 0.0
		total_net_weight = 0.0
		total_gross_weight = 0.0
		total_qty = 0.0
		total_item_amount = 0.0
		total_item_amount_inr = 0.0
		rate_multiplier = flt(self.exchange_rate) if flt(self.exchange_rate) > 0 else 1.0
		doc_before_save = self.get_doc_before_save() if hasattr(self, "get_doc_before_save") else None

		for item in self.get("items", []):
			if item.product:
				if not item.variety:
					item.variety = frappe.db.get_value("Item", item.product, "variety")

				if not item.hsn_code or not item.uom or not item.item_name:
					item_data = frappe.db.get_value("Item", item.product, ["item_name", "gst_hsn_code", "stock_uom"], as_dict=True)
					if item_data:
						if not item.item_name:
							item.item_name = item_data.item_name
						if not item.hsn_code:
							item.hsn_code = item_data.gst_hsn_code
						if not item.uom:
							item.uom = item_data.stock_uom

			# Auto-calculate net_weight if qty was updated via backend or if empty
			if doc_before_save and item.name and item.product:
				old_item = next((d for d in doc_before_save.get("items", []) if d.name == item.name), None)
				if old_item and flt(old_item.qty) != flt(item.qty):
					wpu = flt(frappe.db.get_value("Item", item.product, "weight_per_unit"))
					if wpu > 0:
						item.net_weight = flt(item.qty) * wpu
					elif flt(old_item.qty) > 0 and flt(old_item.net_weight) > 0:
						item.net_weight = (flt(old_item.net_weight) / flt(old_item.qty)) * flt(item.qty)
			elif not flt(item.net_weight) and flt(item.qty) > 0 and item.product:
				wpu = flt(frappe.db.get_value("Item", item.product, "weight_per_unit"))
				if wpu > 0:
					item.net_weight = flt(item.qty) * wpu

			item.amount = flt(item.qty) * flt(item.rate)
			item.base_rate = flt(item.rate) * rate_multiplier
			item.base_amount = flt(item.amount) * rate_multiplier

			total_boxes += flt(item.boxes)
			total_net_weight += flt(item.net_weight)
			total_gross_weight += flt(item.gross_weight)
			total_qty += flt(item.qty)
			total_item_amount += flt(item.amount)
			total_item_amount_inr += flt(item.base_amount)

		self.total_boxes = total_boxes
		self.total_net_weight = total_net_weight
		self.total_gross_weight = total_gross_weight
		self.total_qty = total_qty
		self.total_item_amount = total_item_amount
		self.total_item_amount_inr = total_item_amount_inr

	def calculate_charge_totals(self):
		total_expenses = 0.0
		total_actual_expenses = 0.0

		for charge in self.get("charges", []):
			total_expenses += flt(charge.amount)
			total_actual_expenses += flt(charge.actual_amount)

		self.total_expenses = total_expenses
		self.total_actual_expenses = total_actual_expenses
		self.differ = total_actual_expenses - total_expenses

	def calculate_commercial_totals(self):
		rate = flt(self.exchange_rate) if self.exchange_rate else 1.0
		self.invoice_value_inr = flt(self.invoice_value) * rate
		self.cif_value = flt(self.invoice_value_inr) + flt(self.insurance)

	def update_boe_details(self):
		try:
			from exim.exim.utils.bill_of_entry import get_boe_details_for_shipment

			boe_data = get_boe_details_for_shipment(shipment_doc=self)
			if boe_data and boe_data.get("has_boe"):
				self.duty_basic = flt(boe_data.get("total_customs_duty", 0.0))
				self.cess_and_gst = flt(boe_data.get("total_taxes", 0.0))
				if not self.be_no and boe_data.get("bill_of_entry_no"):
					self.be_no = boe_data.get("bill_of_entry_no")
				if not self.be_date and boe_data.get("bill_of_entry_date"):
					self.be_date = boe_data.get("bill_of_entry_date")
		except Exception:
			pass

	def update_passing_amount(self):
		try:
			# pyrefly: ignore [missing-import]
			from data_sync.data_sync.doc_events.import_shipment import update_passing_amount
			update_passing_amount(self)
		except ImportError:
			pass


@frappe.whitelist()
def get_shipped_qty_for_po_item(po_item_name, exclude_shipment=None):
	"""Returns total quantity already shipped across all non-cancelled Import Shipments for a Purchase Order Item."""
	if not po_item_name:
		return 0.0

	query = """
		SELECT SUM(isi.qty)
		FROM `tabImport Shipment Item` isi
		INNER JOIN `tabImport Shipment` ishp ON ishp.name = isi.parent
		WHERE isi.purchase_order_item = %s
			AND ishp.docstatus != 2
			AND IFNULL(ishp.status, '') != 'Cancelled'
	"""
	params = [po_item_name]
	if exclude_shipment:
		query += " AND ishp.name != %s"
		params.append(exclude_shipment)

	result = frappe.db.sql(query, tuple(params))
	return flt(result[0][0]) if result and result[0] and result[0][0] else 0.0


@frappe.whitelist()
def get_bill_of_entry_details(shipment_name=None, authorized_purchase_invoice=None, be_no=None):
	from exim.exim.utils.bill_of_entry import get_bill_of_entry_details as _get_boe_details

	return _get_boe_details(
		shipment_name=shipment_name,
		authorized_purchase_invoice=authorized_purchase_invoice,
		be_no=be_no,
	)


@frappe.whitelist()
def make_import_shipment(source_name, target_doc=None, args=None):
	if args is None:
		args = {}
	if isinstance(args, str):
		args = json.loads(args)

	mapped_qty_by_item = get_qty_already_mapped(target_doc, "purchase_order_item")

	def select_item(d):
		filtered_items = args.get("filtered_children", [])
		child_filter = d.name in filtered_items if filtered_items else True
		return child_filter

	def update_item(obj, target, source_parent):
		already_shipped = get_shipped_qty_for_po_item(obj.name)
		shipped_or_received = max(flt(obj.received_qty), already_shipped)
		total_mapped_qty = shipped_or_received + flt(mapped_qty_by_item.get(obj.name, 0))
		pending_qty = max(0.0, flt(obj.qty) - total_mapped_qty)

		target.product = obj.item_code
		target.item_name = obj.item_name
		target.hsn_code = getattr(obj, "gst_hsn_code", None) or frappe.db.get_value("Item", obj.item_code, "gst_hsn_code")
		target.variety = getattr(obj, "variety", None) or frappe.db.get_value("Item", obj.item_code, "variety")
		target.qty = pending_qty
		target.uom = obj.uom or getattr(obj, "stock_uom", None)
		target.rate = flt(obj.rate)
		target.amount = pending_qty * flt(obj.rate)

		conversion_rate = flt(getattr(source_parent, "conversion_rate", 1.0)) or 1.0
		target.base_rate = flt(getattr(obj, "base_rate", 0)) or (flt(target.rate) * conversion_rate)
		target.base_amount = pending_qty * flt(target.base_rate)

		target.purchase_order = source_parent.name
		target.purchase_order_item = obj.name

		total_weight = flt(getattr(obj, "total_weight", 0))
		if not total_weight and flt(getattr(obj, "weight_per_unit", 0)):
			total_weight = flt(obj.weight_per_unit) * flt(getattr(obj, "stock_qty", 0) or obj.qty)
		if not total_weight and getattr(obj, "item_code", None):
			item_wpu = flt(frappe.db.get_value("Item", obj.item_code, "weight_per_unit"))
			if item_wpu:
				total_weight = item_wpu * flt(getattr(obj, "stock_qty", 0) or obj.qty)

		if flt(obj.qty) > 0 and pending_qty != flt(obj.qty):
			target.net_weight = (total_weight / flt(obj.qty)) * pending_qty
		else:
			target.net_weight = total_weight

		if getattr(source_parent, "currency", None):
			target.currency = source_parent.currency

	def update_header(source, target):
		if not target.shipper:
			target.shipper = source.supplier
		if getattr(source, "currency", None):
			target.currency = source.currency
		if getattr(source, "company", None):
			target.company = source.company
		if getattr(source, "conversion_rate", None):
			target.exchange_rate = source.conversion_rate

	doc = get_mapped_doc(
		"Purchase Order",
		source_name,
		{
			"Purchase Order": {
				"doctype": "Import Shipment",
				"field_map": {
					"supplier": "shipper",
					"currency": "currency",
					"company": "company",
					"conversion_rate": "exchange_rate",
				},
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Purchase Order Item": {
				"doctype": "Import Shipment Item",
				"field_map": {
					"item_code": "product",
					"name": "purchase_order_item",
					"parent": "purchase_order",
					"gst_hsn_code": "hsn_code",
					"variety": "variety",
					"total_weight": "net_weight",
				},
				"postprocess": update_item,
				"condition": lambda doc: (
					(max(flt(doc.received_qty), get_shipped_qty_for_po_item(doc.name)) + abs(flt(mapped_qty_by_item.get(doc.name, 0)))) < (abs(flt(doc.qty)) - 0.0001)
				)
				and doc.delivered_by_supplier != 1
				and select_item(doc),
			},
		},
		target_doc,
		update_header,
	)

	# Clean up any empty initial item rows or 0 qty rows if present
	if doc.get("items"):
		doc.items = [item for item in doc.items if (item.product or item.qty) and flt(item.qty) > 0]

	doc.run_method("validate")
	return doc


@frappe.whitelist()
def get_charges_for_destination_port(destination_port):
	"""
	Fetch configured service charges from Import Export Charges for the destination port.
	Returns list of dicts: [{'charge_type': service_item, 'item_name': item_name, 'amount': amount}]
	"""
	if not destination_port or not frappe.db.exists("DocType", "Import Export Charges"):
		return []

	charges_doc_name = frappe.db.get_value(
		"Import Export Charges",
		{"port": destination_port, "type": "Import"},
		"name",
	)

	if not charges_doc_name:
		return []

	doc = frappe.get_cached_doc("Import Export Charges", charges_doc_name)
	result = []
	for row in doc.get("charges") or []:
		if not row.service:
			continue
		item_name = frappe.db.get_value("Item", row.service, "item_name") or row.service
		result.append({
			"charge_type": row.service,
			"item_name": item_name,
			"amount": flt(row.amount),
		})

	return result

