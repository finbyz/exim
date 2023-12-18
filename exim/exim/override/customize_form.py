import frappe
from frappe.custom.doctype.customize_form.customize_form import CustomizeForm
from frappe.custom.doctype.property_setter.property_setter import delete_property_setter
import json

class CustomCustomizeForm(CustomizeForm):
	def set_property_setter_for_field_order(self, meta):
		new_order = [df.fieldname for df in self.fields]

		doc_list = frappe.get_list("Field Sequence", pluck='doc_type')

		if self.doc_type in doc_list:
			field_names = frappe.db.get_list("Field Sequence Table", filters={'doc_type': self.doc_type}, fields=['field_name', 'idx'])
			sorted_fields = sorted(field_names, key=lambda x: x['idx'])

			# Remove multiple fields
			fields_to_remove = [field['field_name'] for field in sorted_fields]
			
			new_order = [field for field in new_order if field not in fields_to_remove]

			# Get the index of the standard field "section_break_31"
			sbi = frappe.db.get_value('Field Sequence', {'doc_type': self.doc_type}, ['add_fields_before_section'])
			section_break_index = new_order.index(sbi)

			# Append multiple fields before the standard field "section_break"
			fields_to_append = fields_to_remove
			new_order = new_order[:section_break_index] + fields_to_append + new_order[section_break_index:]

			existing_order = getattr(meta, "field_order", None)
			default_order = [
				fieldname for fieldname, df in meta._fields.items() if not getattr(df, "is_custom_field", False)
			]

			field_order_doc = frappe.db.get_value('Field Order', {'doc_type': self.doc_type}, ['name'])
			if field_order_doc:
				upd_field_order = frappe.get_doc('Field Order', field_order_doc)
				upd_field_order.field_order_list = json.dumps(new_order)
				upd_field_order.save(ignore_permissions=True)
			else:
				new_field_order = frappe.new_doc('Field Order')
				new_field_order.doc_type = self.doc_type
				new_field_order.field_order_list = json.dumps(new_order)
				new_field_order.save(ignore_permissions=True)

			if new_order == default_order:
				if existing_order:
					pass
					# delete_property_setter(self.doc_type, "field_order")

				return

			if existing_order and new_order == json.loads(existing_order):
				return

			frappe.make_property_setter(
				{
					"doctype": self.doc_type,
					"doctype_or_field": "DocType",
					"property": "field_order",
					"value": json.dumps(new_order),
				},
				is_system_generated=True,
			)
		else:
			existing_order = getattr(meta, "field_order", None)
			default_order = [
				fieldname for fieldname, df in meta._fields.items() if not getattr(df, "is_custom_field", False)
			]

			if new_order == default_order:
				if existing_order:
					delete_property_setter(self.doc_type, "field_order")

				return

			if existing_order and new_order == json.loads(existing_order):
				return

			frappe.make_property_setter(
				{
					"doctype": self.doc_type,
					"doctype_or_field": "DocType",
					"property": "field_order",
					"value": json.dumps(new_order),
				},
				is_system_generated=True,
			)