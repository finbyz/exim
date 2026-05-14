# Copyright (c) 2022, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = get_data(filters)
	return columns, data


def get_data(filters):
	columns = [
		dict(label="Invoice No", fieldname="name", fieldtype="Link", options="Sales Invoice", width="250"),
		dict(label="Date", fieldname="posting_date", fieldtype="Date", width="200"),
		dict(label="Port of Loading", fieldname="port_of_loading", fieldtype="Data", width="300"),
		dict(label="Export To (Country)", fieldname="final_destination", fieldtype="Data", width="300"),
		dict(label="Item", fieldname="item_name"),
		dict(label="Qty", fieldname="qty", fieldtype="Float", width="100"),
		dict(label="Uom", fieldname="uom", fieldtype="Link", width="100", options="UOM"),
		dict(label="Fob Value", fieldname="fob_value", fieldtype="Float"),
		dict(label="Container No", fieldname="container_no", fieldtype="Data", width="400"),
	]

	conditions = """
		AND si.gst_category = %s
		AND si.is_opening = %s
		AND si.posting_date BETWEEN %s AND %s
	"""

	query_args = (
		"Overseas",
		"No",
		filters.get("from_date"),
		filters.get("to_date"),
	)

	container_query = """
		SELECT
			cd.container_no,
			si.name
		FROM `tabContainer Details` AS cd
		LEFT JOIN `tabSales Invoice` AS si
			ON cd.parent = si.name
		WHERE si.docstatus = 1
	""" + conditions

	container_details = frappe.db.sql(
		container_query,
		query_args,
		as_dict=1,
	)

	data_query = """
		SELECT
			sii.item_name,
			sii.qty,
			sii.fob_value,
			sii.uom,
			si.name,
			si.posting_date,
			si.port_of_loading,
			si.final_destination
		FROM `tabSales Invoice Item` AS sii
		LEFT JOIN `tabSales Invoice` AS si
			ON sii.parent = si.name
		WHERE si.docstatus = 1
	""" + conditions

	data = frappe.db.sql(
		data_query,
		query_args,
		as_dict=1,
	)

	container_map = {}

	for each in container_details:
		container_map.setdefault(each.name, []).append(each.container_no)

	for each in data:
		each["container_no"] = ",".join(container_map.get(each.name, []))

	return columns, data