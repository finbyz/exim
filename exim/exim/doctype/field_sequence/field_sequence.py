# Copyright (c) 2023, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FieldSequence(Document):
	def before_save(self):
		del_doc_name = frappe.db.get_value('Property Setter', {'doc_type': self.doc_type}, ['name'])
		if del_doc_name:
			frappe.delete_doc('Property Setter', del_doc_name)
	
	def validate(self):
		for row in self.get('field_sequence_table'):
			row.doc_type = self.doc_type
			row.module = self.module
			if row.field_name == self.add_fields_before_section:
				frappe.throw("You can't select the <b>" +row.field_name+"</b> in the Field Sequence Table.")