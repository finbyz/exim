import frappe

def after_migrate():
	field_order_list = frappe.db.get_list('Field Order', pluck='name')
	if field_order_list:
		for list in field_order_list:
			chk_property = frappe.db.get_value('Property Setter', {'doc_type': list, 'property': "field_order"}, ['name'])
			if chk_property:
				frappe.delete_doc('Property Setter', chk_property)
				frappe.db.commit()
				
			chk_field_order = frappe.db.get_value('Field Order', {'doc_type': list}, ['field_order_list'])
			if chk_field_order:
				new_property_setter = frappe.new_doc("Property Setter")
				new_property_setter.doctype_or_field = "DocType"
				new_property_setter.doc_type = list
				new_property_setter.property = "field_order"
				new_property_setter.property_type = "Data"
				new_property_setter.value = chk_field_order
				new_property_setter.flags.ignore_permissions = True
				new_property_setter.insert()
				frappe.db.commit()