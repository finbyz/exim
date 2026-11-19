# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

"""Supplier Quotation Comparison with Import Export (port) charges.

Same as ERPNext's Supplier Quotation Comparison, plus the Tentative Amount from
each quotation's Import Export Charges table. A quotation's charges are split
across its items in proportion to each item's value in company currency, and
the cheapest quote per item is decided on the landed price per stock unit.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.buying.report.supplier_quotation_comparison.supplier_quotation_comparison import (
	get_columns as get_base_columns,
	get_data,
	get_message,
	get_price_per_stock_unit,
	prepare_chart_data,
	validate_filters,
)

CHARGE_DOCTYPE = "Supplier Quotation Import Export Charge"
CHARGE_FIELD = "port_charges"


def execute(filters=None):
	if not filters:
		return [], []

	validate_filters(filters)

	columns = get_columns(filters)
	supplier_quotation_data = get_data(filters)
	allocate_charges(supplier_quotation_data)

	data, chart_data = prepare_data(supplier_quotation_data, filters)

	return columns, data, get_message(), chart_data


def allocate_charges(rows):
	"""Set `port`, `charges_amount` on each quotation item row (company currency)."""
	quotations = list({d.parent for d in rows})
	if not quotations:
		return

	charges = dict(
		frappe.get_all(
			CHARGE_DOCTYPE,
			filters={"parenttype": "Supplier Quotation", "parentfield": CHARGE_FIELD, "parent": ("in", quotations)},
			fields=["parent", {"SUM": "amount", "as": "total"}],
			group_by="parent",
			as_list=True,
		)
	)
	ports = dict(
		frappe.get_all(
			"Supplier Quotation", filters={"name": ("in", quotations)}, fields=["name", "port"], as_list=True
		)
	)

	# Split basis covers every item of the quotation, not only the rows matching the
	# report filters, so an item's share does not change when filtering by item.
	items_by_quotation = defaultdict(list)
	for d in frappe.get_all(
		"Supplier Quotation Item",
		filters={"parent": ("in", quotations), "parenttype": "Supplier Quotation"},
		fields=["parent", "item_code", "base_amount", "qty"],
	):
		items_by_quotation[d.parent].append(d)

	for row in rows:
		row.port = ports.get(row.parent)
		total_charges = flt(charges.get(row.parent))
		row.charges_amount = 0.0
		if not total_charges:
			continue

		siblings = items_by_quotation.get(row.parent) or []
		total_base = sum(flt(d.base_amount) for d in siblings)
		if total_base:
			share = flt(row.base_amount) / total_base
		else:
			total_qty = sum(flt(d.qty) for d in siblings)
			share = flt(row.qty) / total_qty if total_qty else 1.0 / (len(siblings) or 1)

		row.charges_amount = total_charges * share


def prepare_data(supplier_quotation_data, filters):
	out, groups, qty_list, suppliers, chart_data = [], [], [], [], []
	group_wise_map = defaultdict(list)
	supplier_qty_price_map = {}
	rows_by_item = defaultdict(list)

	group_by_field = (
		"supplier_name" if filters.get("categorize_by") == "Categorize by Supplier" else "item_code"
	)
	float_precision = cint(frappe.db.get_default("float_precision")) or 2
	company_currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency")

	for data in supplier_quotation_data:
		group = data.get(group_by_field)

		base_amount = flt(data.get("base_amount"), float_precision)
		charges_amount = flt(data.get("charges_amount"), float_precision)
		landed_amount = flt(base_amount + charges_amount, float_precision)

		row = {
			"item_code": "" if group_by_field == "item_code" else data.get("item_code"),
			"supplier_name": "" if group_by_field == "supplier_name" else data.get("supplier_name"),
			"quotation": data.get("parent"),
			"qty": data.get("qty"),
			"price": flt(data.get("amount"), float_precision),
			"uom": data.get("uom"),
			"price_list_currency": data.get("price_list_currency"),
			"currency": data.get("currency"),
			"company_currency": company_currency,
			"stock_uom": data.get("stock_uom"),
			"base_amount": base_amount,
			"base_rate": flt(data.get("base_rate"), float_precision),
			"port": data.get("port"),
			"charges_amount": charges_amount,
			"landed_amount": landed_amount,
			"request_for_quotation": data.get("request_for_quotation"),
			"valid_till": data.get("valid_till"),
			"lead_time_days": data.get("lead_time_days"),
		}
		row["price_per_unit"] = get_price_per_stock_unit(row["price"], data.get("rate"), data)
		row["base_price_per_unit"] = get_price_per_stock_unit(row["base_amount"], row["base_rate"], data)
		row["landed_price_per_unit"] = get_landed_price_per_unit(landed_amount, row["base_rate"], charges_amount, data)

		group_wise_map[group].append(row)
		rows_by_item[data.get("item_code")].append(row)

		supplier = data.get("supplier_name")
		if filters.get("item_code"):
			qty_prices = supplier_qty_price_map.setdefault(supplier, {})
			qty_prices[row["qty"]] = min(qty_prices.get(row["qty"], landed_amount), landed_amount)

		groups.append(group)
		suppliers.append(supplier)
		qty_list.append(data.get("qty"))

	groups = list(set(groups))
	suppliers = list(set(suppliers))
	qty_list = list(set(qty_list))

	if group_by_field == "item_code" or filters.get("item_code"):
		flag_cheapest_quotes(rows_by_item)

	for group in groups:
		group_entries = group_wise_map[group]
		group_entries[0].update({group_by_field: group})
		out.extend(group_entries)

	if filters.get("item_code"):
		chart_data = prepare_chart_data(suppliers, qty_list, supplier_qty_price_map, company_currency)

	return out, chart_data


def get_landed_price_per_unit(landed_amount, base_rate, charges_amount, data):
	if flt(data.get("stock_qty")):
		return flt(landed_amount) / flt(data.get("stock_qty"))
	qty = flt(data.get("qty"))
	per_uom = flt(base_rate) + (flt(charges_amount) / qty if qty else 0)
	return per_uom / (flt(data.get("conversion_factor")) or 1)


def flag_cheapest_quotes(rows_by_item):
	for rows in rows_by_item.values():
		min_price = min(row["landed_price_per_unit"] for row in rows)
		for row in rows:
			if row["landed_price_per_unit"] == min_price:
				row["min"] = 1


def get_columns(filters):
	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency")
	# "price" (amount in quotation currency) is not needed here
	columns = [c for c in get_base_columns(filters) if c["fieldname"] != "price"]

	charge_columns = [
		{
			"fieldname": "port",
			"label": _("Port"),
			"fieldtype": "Link",
			"options": "Port Details",
			"width": 110,
		},
		{
			"fieldname": "charges_amount",
			"label": _("Tentative Charges ({0})").format(currency),
			"fieldtype": "Currency",
			"options": "company_currency",
			"width": 160,
		},
		{
			"fieldname": "landed_amount",
			"label": _("Amount after Charges ({0})").format(currency),
			"fieldtype": "Currency",
			"options": "company_currency",
			"width": 180,
		},
		{
			"fieldname": "landed_price_per_unit",
			"label": _("Landed Price per Unit ({0})").format(currency),
			"fieldtype": "Currency",
			"options": "company_currency",
			"width": 180,
		},
	]

	insert_at = next(
		(i + 1 for i, c in enumerate(columns) if c["fieldname"] == "base_rate"), len(columns)
	)
	columns[insert_at:insert_at] = charge_columns
	return columns
