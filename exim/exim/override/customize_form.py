import frappe
from frappe.custom.doctype.customize_form.customize_form import CustomizeForm
from frappe.custom.doctype.property_setter.property_setter import delete_property_setter
import json

class CustomCustomizeForm(CustomizeForm):
	def set_property_setter_for_field_order(self, meta):
		new_order = [df.fieldname for df in self.fields]

		doc_list = frappe.get_list("Field Sequence", pluck='doc_type')

		if self.doc_type in doc_list:
			default_module = frappe.db.get_single_value("Field Sequence Settings", "module")
			if not default_module:
				frappe.throw("Please set the module in Field Sequence Settings.")
			field_names = frappe.get_all("Field Sequence Table", filters={'parent': self.doc_type, 'module': default_module}, fields=['field_name', 'idx'])
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
				is_system_generated=False,
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
				is_system_generated=False,
			)