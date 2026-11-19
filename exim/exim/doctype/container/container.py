# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Container(Document):
	def validate(self):
		if not self.container_name and self.container_no:
			self.container_name = self.container_no

		old_doc = self.get_doc_before_save() if callable(getattr(self, "get_doc_before_save", None)) else None
		if old_doc:
			if self.disable and not old_doc.disable:
				self.enable = 0
			elif self.enable and not old_doc.enable:
				self.disable = 0
			elif self.disable and self.enable:
				self.enable = 0
			elif not self.disable and not self.enable:
				self.enable = 1
		else:
			if self.disable:
				self.enable = 0
			else:
				self.enable = 1
