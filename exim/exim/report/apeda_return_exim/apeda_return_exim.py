# Copyright (c) 2022, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns, data = get_data(filters)
	return columns, data

def get_data(filters):
	columns=[
		dict(label="Invoice No", fieldname="name", fieldtype="Link", options="Sales Invoice",width="250"),
		dict(label="Date", fieldname="posting_date", fieldtype="Date",width="200"),
		dict(label="Port of Loading", fieldname="port_of_loading", fieldtype="Data",width="300"),
		dict(label="Export To (Country)", fieldname="final_destination", fieldtype="Data",width="300"),
		dict(label="Item", fieldname="item_name"),
		dict(label="Qty", fieldname="qty", fieldtype="Float",width="100"),
		dict(label="Uom", fieldname="uom", fieldtype="Link",width="100",options="UOM"),
		dict(label="Fob Value", fieldname="fob_value", fieldtype="Float"),
		dict(label="Container No", fieldname="container_no", fieldtype="Data",width="400")
		]



	conditions=f"and si.gst_category = 'Overseas' and si.is_opening='No' and si.posting_date between '{filters.get('from_date')}' and '{filters.get('to_date')}' "

	
	container_details=frappe.db.sql(f"""
	select cd.container_no,si.name
	from `tabContainer Details` as cd
	left join `tabSales Invoice` as si on cd.parent = si.name
	where si.docstatus=1 {conditions}
	""",as_dict=1)

	data=frappe.db.sql(f"""
	select sii.item_name,sii.qty,sii.fob_value,sii.uom,si.name,si.posting_date,si.port_of_loading,si.final_destination
	from `tabSales Invoice Item` as sii
	left join `tabSales Invoice` as si on sii.parent = si.name
	where si.docstatus=1 {conditions}
	""",as_dict=1)
	container_map={}
	for each in container_details:
		container_map.setdefault(each.name,[]).append(each.container_no)

	for each in data:
		each['container_no']=','.join(container_map.get(each.name,[]))
	
	return columns,data