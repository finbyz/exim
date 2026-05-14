import frappe

@frappe.whitelist()
def get_invoce_no(doctype, txt, searchfield, start, page_len, filters):

	if not filters.get("invoice_no"):
		return []

	return frappe.db.sql(
		"""
		SELECT DISTINCT parent
		FROM `tabPayment Entry Reference`
		WHERE reference_name = %s
		""",
		(filters.get("invoice_no"),)
	)


@frappe.whitelist()
def get_invoce_no_based_on_customer(
	doctype,
	txt,
	searchfield,
	start,
	page_len,
	filters
):

	conditions = ""
	query_args = []

	if txt:
		conditions += " AND si.name LIKE %s"
		query_args.append(f"%{txt}%")

	query = """
		SELECT DISTINCT si.name
		FROM `tabSales Invoice` si
		LEFT JOIN `tabAddress` ad
			ON ad.name = si.customer_address
		WHERE ad.country != %s
			AND si.docstatus = 1
	"""

	query_args.insert(0, "India")

	query += conditions

	return frappe.db.sql(
		query,
		tuple(query_args)
	)