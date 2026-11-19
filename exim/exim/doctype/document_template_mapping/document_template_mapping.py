# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DocumentTemplateMapping(Document):
	# Adding the checklist fields to the target DocType is done by the constro_chem app
	# (doc_events "Document Template Mapping" on_update), so this app does not depend on it.
	def validate(self):
		self.validate_condition()

	def validate_condition(self):
		if self.condition:
			# Test compile the expression
			try:
				compile(self.condition.strip(), "<string>", "eval")
			except Exception as e:
				frappe.throw(_("Invalid Python condition syntax: {0}").format(str(e)))
