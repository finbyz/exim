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
		self.validate_container_details_items()
		self.set_container_boxes_and_weight()
		self.set_container_summary()
		self.calculate_week()
		self.calculate_item_totals()
		self.calculate_charge_totals()
		self.calculate_rates()
		self.sync_commercial_details_from_pi()
		self.calculate_commercial_totals()

	def validate_container_details_items(self):
		if not self.get("container_details"):
			return

		valid_items = {
			row.get("product") or row.get("item_code")
			for row in (self.get("items") or [])
			if (row.get("product") or row.get("item_code"))
		}

		invalid_rows = []
		for idx, row in enumerate(self.get("container_details") or [], start=1):
			item_code = row.get("item_code")
			if item_code and item_code not in valid_items:
				row_idx = row.get("idx") or idx
				invalid_rows.append(
					_("Row #{0}: Item {1} is not present in Shipment Items table.").format(
						row_idx, frappe.bold(item_code)
					)
				)

		if invalid_rows:
			frappe.throw("<br>".join(invalid_rows), title=_("Invalid Container Item"))

	def set_container_boxes_and_weight(self):
		"""Fill blank Boxes / Net Weight of container rows from the Shipment Items table
		(same item), split by the row's qty: item value x row qty / item qty.
		No qty on the row means the whole item is in that container.
		Values entered by the user are kept."""
		totals = {}
		for item in self.get("items") or []:
			code = item.get("product") or item.get("item_code")
			if not code:
				continue
			t = totals.setdefault(code, frappe._dict(qty=0.0, boxes=0.0, net_weight=0.0))
			t.qty += flt(item.qty)
			t.boxes += flt(item.boxes)
			t.net_weight += flt(item.net_weight)

		for row in self.get("container_details") or []:
			t = totals.get(row.item_code)
			if not t:
				continue
			ratio = flt(row.qty) / t.qty if flt(row.qty) and t.qty else 1
			if not flt(row.boxes):
				row.boxes = flt(t.boxes * ratio, row.precision("boxes"))
			if not flt(row.net_weight):
				row.net_weight = flt(t.net_weight * ratio, row.precision("net_weight"))

	def set_container_summary(self):
		"""No of Cont / Container Nos are read only: set them from the Container Details table.
		Older shipments without container rows keep their existing values."""
		containers = list(dict.fromkeys(row.container for row in self.get("container_details") or [] if row.container))
		if containers:
			self.no_of_containers = len(containers)
			self.container_nos = ", ".join(containers)

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

			# Boxes / Net Wt from the Item's UOM factors (factor = units of that UOM in one Box)
			if set_boxes_and_net_weight(item):
				pass
			# Fallback: Item has no Kg factor. Auto-calculate net_weight if qty changed or if empty
			elif doc_before_save and item.name and item.product:
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
			set_passing_rate_per_kg(item, rate_multiplier)

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

	def sync_custom_duty_charge(self):
		duty = flt(self.duty_basic)
		if duty <= 0:
			return

		item_code = "Custom Duty"
		item_name = frappe.db.get_value("Item", item_code, "item_name") or "Custom Duty"

		custom_duty_row = None
		empty_row = None

		for row in self.get("charges", []):
			if row.charge_type in ("Custom Duty", item_code):
				custom_duty_row = row
				break
			elif not row.charge_type and not flt(row.amount) and not flt(row.actual_amount):
				if empty_row is None:
					empty_row = row

		if custom_duty_row:
			custom_duty_row.charge_type = item_code
			custom_duty_row.amount = duty
			custom_duty_row.actual_amount = duty
			if not custom_duty_row.item_name:
				custom_duty_row.item_name = item_name
		elif empty_row:
			empty_row.charge_type = item_code
			empty_row.item_name = item_name
			empty_row.amount = duty
			empty_row.actual_amount = duty
		else:
			self.append(
				"charges",
				{
					"charge_type": item_code,
					"item_name": item_name,
					"amount": duty,
					"actual_amount": duty,
				},
			)

	def sync_commercial_details_from_pi(self):
		pi_name = self.authorized_purchase_invoice or self.purchase_invoice
		if not pi_name and self.name and not self.name.startswith("new-"):
			pi_name = frappe.db.get_value(
				"Purchase Invoice",
				{"import_shipment": self.name, "docstatus": ["!=", 2]},
				"name",
				order_by="docstatus desc, creation desc",
			)
			if pi_name:
				is_auth = frappe.db.get_value("Purchase Invoice", pi_name, "authority")
				if is_auth and str(is_auth).strip().lower() == "authorized":
					self.authorized_purchase_invoice = pi_name
				else:
					self.purchase_invoice = pi_name

		if not pi_name:
			doc_before_save = self.get_doc_before_save() if hasattr(self, "get_doc_before_save") else None
			if doc_before_save and (doc_before_save.purchase_invoice or doc_before_save.authorized_purchase_invoice):
				self.invoice_value = 0.0
				self.invoice_value_inr = 0.0
				self.cif_value = flt(self.insurance)
				self.invoice_no = None
			return

		pi_data = frappe.db.get_value(
			"Purchase Invoice",
			pi_name,
			[
				"grand_total",
				"base_grand_total",
				"conversion_rate",
				"bill_no",
				"bill_date",
				"posting_date",
				"currency",
				"docstatus",
			],
			as_dict=True,
		)
		if not pi_data:
			return

		inv_val = flt(pi_data.grand_total)
		conv_rate = flt(pi_data.conversion_rate) if flt(pi_data.conversion_rate) > 0 else (flt(self.exchange_rate) or 1.0)
		inv_val_inr = flt(pi_data.base_grand_total) if flt(pi_data.base_grand_total) > 0 else (inv_val * conv_rate)

		if inv_val > 0 or not flt(self.invoice_value):
			self.invoice_value = inv_val
			self.exchange_rate = conv_rate
			self.invoice_value_inr = inv_val_inr
			self.cif_value = inv_val_inr + flt(self.insurance)

		if not self.invoice_no and (pi_data.bill_no or pi_name):
			self.invoice_no = pi_data.bill_no or pi_name
		if not self.invoice_date and (pi_data.bill_date or pi_data.posting_date):
			self.invoice_date = pi_data.bill_date or pi_data.posting_date
		if pi_data.currency and not self.currency:
			self.currency = pi_data.currency

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
	"""Import charges configured for the destination port (Import Export Charges)."""
	from exim.exim.utils.port_charges import get_port_charges

	return get_port_charges(destination_port, "Import")


BOX_UOMS = ("box", "boxes", "ctn", "carton")
KG_UOMS = ("kg", "kgs")


@frappe.whitelist()
def get_item_uom_factors(item_code):
	"""{"stock_uom": .., "factors": {uom: factor}} where factor = units of that UOM in one stock unit (Box)."""
	if not item_code:
		return {}
	frappe.has_permission("Item", "read", item_code, throw=True)
	return _get_item_uom_factors(item_code)


def _get_item_uom_factors(item_code):
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	rows = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code, "parenttype": "Item"},
		fields=["uom", "conversion_factor"],
	)
	factors = {r.uom: flt(r.conversion_factor) for r in rows if flt(r.conversion_factor)}
	if stock_uom:
		factors.setdefault(stock_uom, 1.0)
	return {"stock_uom": stock_uom, "factors": factors}


def _factor_for(factors, names):
	return next((f for uom, f in factors.items() if (uom or "").strip().lower() in names), 0)


def set_boxes_and_net_weight(item):
	"""Boxes = Qty / factor(UOM); Net Wt (kg) = Boxes x factor(Kg). Returns False if Item has no Kg factor."""
	if not (item.product and flt(item.qty)):
		return False

	data = _get_item_uom_factors(item.product)
	factors = data.get("factors") or {}
	kg_factor = _factor_for(factors, KG_UOMS)
	uom_factor = factors.get(item.uom or data.get("stock_uom"))
	if not (kg_factor and uom_factor):
		return False

	stock_units = flt(item.qty) / uom_factor  # in stock UOM (Box)
	box_factor = factors.get(data.get("stock_uom")) if (data.get("stock_uom") or "").lower() in BOX_UOMS else _factor_for(factors, BOX_UOMS)
	item.boxes = stock_units * (box_factor or 1)
	item.net_weight = stock_units * kg_factor
	return True


def set_passing_rate_per_kg(item, exchange_rate):
	"""Passing Rate per KG = Passing Rate / (Net Wt / Qty), in INR and in the shipment currency (USD)."""
	if not item.meta.has_field("passing_rate_per_kg"):
		return
	kg_per_unit = flt(item.net_weight) / flt(item.qty) if flt(item.qty) else 0
	passing_rate = flt(item.get("passing_rate"))
	item.passing_rate_per_kg = (passing_rate * flt(exchange_rate)) / kg_per_unit if kg_per_unit else 0
	if item.meta.has_field("passing_rate_per_kg_usd"):
		item.passing_rate_per_kg_usd = passing_rate / kg_per_unit if kg_per_unit else 0


@frappe.whitelist()
def get_link_documents(shipment):
	"""Documents linked to an Import Shipment, as [{doctype, names, has_link_field}] for the Link Documents section."""
	frappe.has_permission("Import Shipment", "read", shipment, throw=True)

	def has_field(doctype, fieldname="import_shipment"):
		return bool(frappe.db.exists("DocType", doctype)) and frappe.get_meta(doctype).has_field(fieldname)

	def unique(names):
		return list(dict.fromkeys(n for n in names if n))

	def by_field(doctype):
		if not has_field(doctype):
			return []
		return frappe.get_all(doctype, filters={"import_shipment": shipment}, pluck="name", order_by="creation")

	# Purchase Orders: the shipment's item rows, plus any PO tagged with the shipment
	po = unique(
		frappe.get_all(
			"Import Shipment Item",
			filters={"parent": shipment, "parenttype": "Import Shipment", "purchase_order": ("is", "set")},
			pluck="purchase_order",
			order_by="idx",
		)
		+ by_field("Purchase Order")
	)

	pi = by_field("Purchase Invoice")
	if has_field("Purchase Invoice Item"):
		pi += frappe.get_all(
			"Purchase Invoice Item",
			filters={"import_shipment": shipment, "parenttype": "Purchase Invoice"},
			pluck="parent",
		)
	pi += [v for v in frappe.db.get_value("Import Shipment", shipment, ["purchase_invoice", "authorized_purchase_invoice"]) or [] if v]
	if po:
		pi += frappe.get_all(
			"Purchase Invoice Item", filters={"purchase_order": ("in", po), "parenttype": "Purchase Invoice"}, pluck="parent"
		)
	pi = unique(pi)

	pr = []
	if pi:
		pr += frappe.get_all(
			"Purchase Receipt Item", filters={"purchase_invoice": ("in", pi), "parenttype": "Purchase Receipt"}, pluck="parent"
		)
		pr += frappe.get_all(
			"Purchase Invoice Item", filters={"parent": ("in", pi), "purchase_receipt": ("is", "set")}, pluck="purchase_receipt"
		)
	if po:
		pr += frappe.get_all(
			"Purchase Receipt Item", filters={"purchase_order": ("in", po), "parenttype": "Purchase Receipt"}, pluck="parent"
		)

	boe = []
	if pi and frappe.db.exists("DocType", "Bill of Entry Item"):
		boe = frappe.get_all(
			"Bill of Entry Item", filters={"purchase_invoice": ("in", pi), "parenttype": "Bill of Entry"}, pluck="parent"
		)

	pe = []
	for ref_doctype, names in (("Purchase Invoice", pi), ("Purchase Order", po)):
		if names:
			pe += frappe.get_all(
				"Payment Entry Reference",
				filters={"reference_doctype": ref_doctype, "reference_name": ("in", names), "parenttype": "Payment Entry"},
				pluck="parent",
			)

	linked = [
		("Purchase Order", po),
		("Purchase Receipt", unique(pr)),
		("Unloading Checklist", by_field("Unloading Checklist")),
		("Purchase Invoice", pi),
		("Bill of Entry", unique(boe)),
		("Payment Entry", unique(pe)),
	]
	out = []
	for doctype, names in linked:
		if not frappe.db.exists("DocType", doctype):
			continue
		readable = bool(frappe.has_permission(doctype, "read"))
		out.append(
			{
				"doctype": doctype,
				"names": unique(names) if readable else [],
				"can_create": bool(frappe.has_permission(doctype, "create")),
				"has_link_field": has_field(doctype),
			}
		)
	return out
