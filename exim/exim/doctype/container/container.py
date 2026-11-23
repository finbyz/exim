# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class Container(Document):
	# Single "Enable" check (default 1). Untick it to disable the container;
	# disabled containers are not offered in Import Shipment / Serial and Batch.
	def validate(self):
		if not self.container_name and self.container_no:
			self.container_name = self.container_no
