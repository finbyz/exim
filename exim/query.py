import frappe

@frappe.whitelist()
def get_invoce_no(doctype, txt, searchfield, start, page_len, filters):
	if filters.get("invoice_no"):
		return frappe.db.sql(f"""select distinct parent from `tabPayment Entry Reference` where reference_name = '{filters.get('invoice_no')}' """)
	

@frappe.whitelist()
def get_invoce_no_based_on_customer(doctype, txt, searchfield, start, page_len, filters):
		return frappe.db.sql(f"""
			select distinct si.name
			from `tabSales Invoice` si
			LEFT JOIN `tabAddress` as ad ON ad.name = si.customer_address
			where ad.country != "India" and si.docstatus = 1
		""")
	