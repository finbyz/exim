# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

"""Supplier Quotation Comparison with Import Export (port) charges.

Same as ERPNext's Supplier Quotation Comparison, plus the Tentative Amount from
each quotation's Import Export Charges table. A quotation's charges are split
across its items in proportion to each item's amount in company currency (or its qty, per the
"Split Charges" filter), the same "By Amount" / "By Qty" split used on Jasma, and
the cheapest quote per item is decided on the landed price per stock unit.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.setup.utils import get_exchange_rate

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
# extra landed cost column shown in this currency
LANDED_FOREIGN_CURRENCY = "USD"


def execute(filters=None):
	if not filters:
		return [], []

	validate_filters(filters)

	columns = get_columns(filters)
	supplier_quotation_data = get_data(filters)
	allocate_charges(supplier_quotation_data)

	data, chart_data = prepare_data(supplier_quotation_data, filters)
	if not chart_data:
		chart_data = get_supplier_chart(supplier_quotation_data, filters)

	return columns, data, get_message(), chart_data, get_report_summary(supplier_quotation_data, filters)


def get_report_summary(rows, filters):
	"""Summary cards: counts, price, charges and landed amount (company currency)."""
	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency")
	key = get_splits(filters)[0]

	price = sum(flt(d.base_amount) for d in rows)
	charges = sum(flt(d.get(f"{key}_charges")) for d in rows)

	def money(label, value, indicator):
		return {"value": value, "label": label, "datatype": "Currency", "currency": currency, "indicator": indicator}

	def count(label, value, indicator):
		return {"value": value, "label": label, "datatype": "Int", "indicator": indicator}

	return [
		count(_("Quotations"), len({d.parent for d in rows}), "Blue"),
		count(_("Suppliers"), len({d.supplier_name for d in rows}), "Purple"),
		count(_("Items"), len({d.item_code for d in rows}), "Cyan"),
		money(_("Total Price"), price, "Blue"),
		money(_("Total Charges"), charges, "Orange"),
		money(_("Amount after Charges"), price + charges, "Green"),
	]


def get_supplier_chart(rows, filters):
	"""Stacked bar per supplier: price and charges (company currency), largest 12 suppliers."""
	if not rows:
		return None

	key = get_splits(filters)[0]
	price, charges = defaultdict(float), defaultdict(float)
	for d in rows:
		price[d.supplier_name] += flt(d.base_amount)
		charges[d.supplier_name] += flt(d.get(f"{key}_charges"))

	suppliers = sorted(price, key=lambda name: price[name] + charges[name], reverse=True)[:12]
	return {
		"data": {
			"labels": suppliers,
			"datasets": [
				{"name": _("Price"), "values": [flt(price[name], 2) for name in suppliers]},
				{"name": _("Charges"), "values": [flt(charges[name], 2) for name in suppliers]},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
		"colors": ["#2563EB", "#F59E0B"],
		"fieldtype": "Currency",
	}


SPLITS = {"amount": "Amount Wise", "qty": "Qty Wise"}


def get_splits(filters):
	"""Selected charge splits, in display order. Amount Wise when nothing is ticked."""
	selected = [key for key in SPLITS if cint(filters.get(f"{key}_wise"))]
	return selected or ["amount"]


def allocate_charges(rows):
	"""Set `port` and, for both splits, `<key>_ratio` (%) and `<key>_charges` (company currency).

	Amount wise shares a quotation's charges by each item's amount in company currency, qty wise by
	each item's quantity.
	"""
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
	quotation_details = {
		d.name: d
		for d in frappe.get_all(
			"Supplier Quotation",
			filters={"name": ("in", quotations)},
			fields=["name", "port", "currency", "conversion_rate", "transaction_date"],
		)
	}

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
		details = quotation_details.get(row.parent) or frappe._dict()
		row.port = details.port
		row.quotation_conversion_rate = details.conversion_rate
		row.transaction_date = details.transaction_date
		total_charges = flt(charges.get(row.parent))
		siblings = items_by_quotation.get(row.parent) or []
		total_amount = sum(flt(d.base_amount) for d in siblings)
		total_qty = sum(flt(d.qty) for d in siblings)
		even = 1.0 / (len(siblings) or 1)

		shares = {
			"amount": flt(row.base_amount) / total_amount if total_amount else even,
			"qty": flt(row.qty) / total_qty if total_qty else even,
		}
		for key, share in shares.items():
			row[f"{key}_ratio"] = share * 100 if total_charges else 0.0
			row[f"{key}_charges"] = total_charges * share


def prepare_data(supplier_quotation_data, filters):
	out, groups, qty_list, suppliers, chart_data = [], [], [], [], []
	group_wise_map = defaultdict(list)
	supplier_qty_price_map = {}
	rows_by_item = defaultdict(list)
	splits = get_splits(filters)

	group_by_field = (
		"supplier_name" if filters.get("categorize_by") == "Categorize by Supplier" else "item_code"
	)
	float_precision = cint(frappe.db.get_default("float_precision")) or 2
	company_currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency")
	exchange_rates = {}

	for data in supplier_quotation_data:
		group = data.get(group_by_field)

		base_amount = flt(data.get("base_amount"), float_precision)

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
			"landed_foreign_currency": LANDED_FOREIGN_CURRENCY,
			"stock_uom": data.get("stock_uom"),
			"base_amount": base_amount,
			"base_rate": flt(data.get("base_rate"), float_precision),
			"port": data.get("port"),
			"request_for_quotation": data.get("request_for_quotation"),
			"valid_till": data.get("valid_till"),
			"lead_time_days": data.get("lead_time_days"),
		}
		row["price_per_unit"] = get_price_per_stock_unit(row["price"], data.get("rate"), data)
		row["base_price_per_unit"] = get_price_per_stock_unit(row["base_amount"], row["base_rate"], data)

		for key in splits:
			charges_amount = flt(data.get(f"{key}_charges"), float_precision)
			landed_amount = flt(base_amount + charges_amount, float_precision)
			row[f"{key}_ratio"] = flt(data.get(f"{key}_ratio"), float_precision)
			row[f"{key}_charges"] = charges_amount
			row[f"{key}_landed_amount"] = landed_amount
			row[f"{key}_landed_price_per_unit"] = get_landed_price_per_unit(
				landed_amount, row["base_rate"], charges_amount, data
			)
			row[f"{key}_landed_price_per_unit_foreign"] = flt(
				row[f"{key}_landed_price_per_unit"]
				/ get_foreign_exchange_rate(data, company_currency, exchange_rates),
				float_precision,
			)

		# the chart and the price per box follow the first selected split
		landed_amount = row[f"{splits[0]}_landed_amount"]
		row["price_per_box"] = flt(landed_amount / flt(data.get("qty")), float_precision) if flt(data.get("qty")) else 0

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
		flag_cheapest_quotes(rows_by_item, splits)

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


def get_foreign_exchange_rate(data, company_currency, cache):
	"""Company-currency units per 1 LANDED_FOREIGN_CURRENCY (USD).

	Uses the quotation's own conversion rate when it is in USD, else the exchange rate
	on the quotation date.
	"""
	if company_currency == LANDED_FOREIGN_CURRENCY:
		return 1.0
	if data.get("currency") == LANDED_FOREIGN_CURRENCY and flt(data.get("quotation_conversion_rate")):
		return flt(data.get("quotation_conversion_rate"))

	date = data.get("transaction_date")
	if date not in cache:
		cache[date] = flt(get_exchange_rate(LANDED_FOREIGN_CURRENCY, company_currency, date)) or 1.0
	return cache[date]


def flag_cheapest_quotes(rows_by_item, splits):
	for rows in rows_by_item.values():
		for key in splits:
			field = f"{key}_landed_price_per_unit"
			min_price = min(row[field] for row in rows)
			for row in rows:
				if row[field] == min_price:
					row[f"min_{key}"] = 1


def get_columns(filters):
	"""Column order: Price per Unit, Price Per Unit (INR), Landed Price per Unit (INR),
	Landed Cost Per Unit (USD), Charge Share (%), Price per Box, Charges,
	Amount after Charges, Port, then the rest of the base columns.
	"""
	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency")
	# not shown: "price" (amount in quotation currency), "base_amount" (Price in company currency),
	# "stock_uom" and "currency"
	hidden = ("price", "base_amount", "stock_uom", "currency")
	columns = [c for c in get_base_columns(filters) if c["fieldname"] not in hidden]

	charge_columns = []
	for key in get_splits(filters):
		charge_columns += [
			{
				"fieldname": f"{key}_landed_price_per_unit",
				"label": _("Landed Price per Unit ({0})").format(currency),
				"fieldtype": "Currency",
				"options": "company_currency",
				"width": 180,
			},
			{
				"fieldname": f"{key}_landed_price_per_unit_foreign",
				"label": _("Landed Cost Per Unit ({0})").format(LANDED_FOREIGN_CURRENCY),
				"fieldtype": "Currency",
				"options": "landed_foreign_currency",
				"width": 180,
			},
			{
				"fieldname": f"{key}_ratio",
				"label": _("Charge Share (%)"),
				"fieldtype": "Percent",
				"width": 130,
			},
		]

	charge_columns.append(
		{
			"fieldname": "price_per_box",
			"label": _("Price per Box ({0})").format(currency),
			"fieldtype": "Currency",
			"options": "company_currency",
			"width": 150,
		}
	)

	for key in get_splits(filters):
		charge_columns += [
			{
				"fieldname": f"{key}_charges",
				"label": _("Charges ({0})").format(currency),
				"fieldtype": "Currency",
				"options": "company_currency",
				"width": 160,
			},
			{
				"fieldname": f"{key}_landed_amount",
				"label": _("Amount after Charges ({0})").format(currency),
				"fieldtype": "Currency",
				"options": "company_currency",
				"width": 190,
			},
		]

	charge_columns.append(
		{
			"fieldname": "port",
			"label": _("Port"),
			"fieldtype": "Link",
			"options": "Port Details",
			"width": 110,
		}
	)

	insert_at = next(
		(i + 1 for i, c in enumerate(columns) if c["fieldname"] == "base_rate"), len(columns)
	)
	columns[insert_at:insert_at] = charge_columns
	return columns
