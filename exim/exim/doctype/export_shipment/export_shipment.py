# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


# latest milestone first
STATUS_BY_DATE = (
	("delivered_on", "Delivered"),
	("arrived_on", "Arrived"),
	("shipped_on", "Shipped"),
	("loading_date", "Loading"),
)


class ExportShipment(Document):
	def before_insert(self):
		self.set_shipment_no()

	def validate(self):
		self.set_shipment_no()
		self.set_defaults()
		self.set_notify_party_address()
		self.validate_dates()
		self.set_status()
		self.validate_sales_invoices()
		self.set_container_summary()
		self.calculate_charge_totals()
		self.calculate_final_costing()

	def on_update(self):
		if not self.shipment_no and self.name and not self.name.startswith("new-"):
			self.db_set("shipment_no", self.name, update_modified=False)

	def set_shipment_no(self):
		if not self.shipment_no and self.name and not self.name.startswith("new-"):
			self.shipment_no = self.name

	def set_defaults(self):
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
				"Global Defaults", "default_company"
			)
		# customer can be fetched from the Sales Order after customer_name was processed
		self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name") if self.customer else None
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")

	def set_notify_party_address(self):
		from frappe.contacts.doctype.address.address import get_address_display

		self.notify_party_address = get_address_display(self.notify_party) if self.notify_party else ""

	def validate_dates(self):
		if self.etd and self.eta and getdate(self.eta) < getdate(self.etd):
			frappe.throw(_("ETA cannot be before ETD."))

		# milestone dates that are filled must be in order
		filled = [(f, self.get(f)) for f, _status in reversed(STATUS_BY_DATE) if self.get(f)]
		for (prev_field, prev_date), (field, date) in zip(filled, filled[1:]):
			if getdate(date) < getdate(prev_date):
				frappe.throw(
					_("{0} cannot be before {1}.").format(
						_(self.meta.get_label(field)), _(self.meta.get_label(prev_field))
					)
				)

	def set_status(self):
		"""Status follows the latest milestone date filled. Final Costing is set from the
		form button once Delivered, and is kept while Delivered On is filled."""
		if self.status == "Final Costing" and self.delivered_on:
			return
		self.status = next((status for field, status in STATUS_BY_DATE if self.get(field)), "Planning")

	def validate_sales_invoices(self):
		"""Sales Invoice No against a container: same customer, not cancelled, and not used
		on another Export Shipment. One invoice may cover several containers of this shipment."""
		invoices = {row.sales_invoice for row in self.get("containers") or [] if row.sales_invoice}
		if not invoices:
			return

		si_data = {
			d.name: d
			for d in frappe.get_all(
				"Sales Invoice",
				filters={"name": ("in", list(invoices))},
				fields=["name", "customer", "docstatus", "export_shipment"]
				if frappe.get_meta("Sales Invoice").has_field("export_shipment")
				else ["name", "customer", "docstatus"],
			)
		}

		used_elsewhere = {
			d.sales_invoice: d.parent
			for d in frappe.get_all(
				"Export Shipment Container",
				filters={
					"sales_invoice": ("in", list(invoices)),
					"parenttype": "Export Shipment",
					"parent": ("!=", self.name or ""),
				},
				fields=["sales_invoice", "parent"],
			)
		}

		errors = []
		for row in self.get("containers") or []:
			si = si_data.get(row.sales_invoice)
			if not si:
				continue
			if si.docstatus == 2:
				errors.append(_("Row #{0}: Sales Invoice {1} is cancelled.").format(row.idx, frappe.bold(si.name)))
			elif self.customer and si.customer != self.customer:
				errors.append(
					_("Row #{0}: Sales Invoice {1} is for customer {2}, not {3}.").format(
						row.idx, frappe.bold(si.name), si.customer, self.customer
					)
				)
			elif si.name in used_elsewhere:
				errors.append(
					_("Row #{0}: Sales Invoice {1} is already recorded on Export Shipment {2}.").format(
						row.idx, frappe.bold(si.name), used_elsewhere[si.name]
					)
				)
			elif si.get("export_shipment") and si.export_shipment != self.name:
				errors.append(
					_("Row #{0}: Sales Invoice {1} is linked to Export Shipment {2}.").format(
						row.idx, frappe.bold(si.name), si.export_shipment
					)
				)

		if errors:
			frappe.throw("<br>".join(dict.fromkeys(errors)), title=_("Invalid Sales Invoice"))

	def set_container_summary(self):
		containers = list(dict.fromkeys(row.container for row in self.get("containers") or [] if row.container))
		self.no_of_containers = len(containers)
		self.container_nos = ", ".join(containers)
		self.total_boxes = sum(flt(row.boxes) for row in self.get("containers") or [])
		self.total_net_weight = sum(flt(row.net_weight) for row in self.get("containers") or [])
		self.total_gross_weight = sum(flt(row.gross_weight) for row in self.get("containers") or [])

	def calculate_charge_totals(self):
		by_category = {"Shipping Line": 0.0, "Transport": 0.0, "Other": 0.0}
		total = actual = differ = 0.0
		for row in self.get("charges") or []:
			# category totals use the actual amount once entered, else the tentative amount
			value = flt(row.actual_amount) or flt(row.amount)
			key = row.charge_category if row.charge_category in by_category else "Other"
			by_category[key] += value
			total += flt(row.amount)
			actual += flt(row.actual_amount)
			if flt(row.actual_amount):
				differ += flt(row.actual_amount) - flt(row.amount)

		self.total_shipping_line_charges = by_category["Shipping Line"]
		self.total_transport_charges = by_category["Transport"]
		self.total_other_charges = by_category["Other"]
		self.total_expenses = total
		self.total_actual_expenses = actual
		self.differ = differ  # only rows with an actual amount

	def calculate_final_costing(self):
		invoices = list({row.sales_invoice for row in self.get("containers") or [] if row.sales_invoice})
		sales_value = 0.0
		if invoices:
			sales_value = flt(
				frappe.get_all(
					"Sales Invoice",
					filters={"name": ("in", invoices), "docstatus": 1},
					fields=[{"SUM": "base_net_total", "as": "total"}],
				)[0].total
			)
		charges = sum(flt(row.actual_amount) or flt(row.amount) for row in self.get("charges") or [])
		self.total_sales_value = sales_value
		self.net_value_after_charges = sales_value - charges


@frappe.whitelist()
def get_export_port_charges(port):
	"""Export charges configured for the port of loading (Import Export Charges, type Export)."""
	frappe.has_permission("Export Shipment", "read", throw=True)
	from exim.exim.utils.port_charges import get_port_charges

	return get_port_charges(port, "Export")
