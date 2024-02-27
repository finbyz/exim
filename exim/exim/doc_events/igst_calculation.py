import frappe

def cal_igst(self, method):
	# for Overseas or SEZ
	if self.gst_category == "Overseas" or self.gst_category == "SEZ":
		igst_acc = frappe.db.get_value('GST Account', {'parent': 'GST Settings', 'company': self.company, 'account_type': "Output"}, ['igst_account'])
		if igst_acc:
			if not self.taxes:
				zero_igst(self)
			else:
				for tax in self.taxes:
					if tax.account_head == igst_acc:
						item_wise_tax_detail = tax.item_wise_tax_detail
						
						# Check if item_wise_tax_detail is a string and convert it to a dictionary
						if isinstance(item_wise_tax_detail, str):
							item_wise_tax_detail = frappe.parse_json(item_wise_tax_detail)
						
						for item, tax_detail in item_wise_tax_detail.items():
							igst_rate, igst_amount = tax_detail
							update_sales_invoice_item(self, item, igst_rate, igst_amount)
					else:
						zero_igst(self)

def update_sales_invoice_item(self, item_code, igst_rate, igst_amount):
	# Find the Sales Invoice Item corresponding to the item_code
	for item in self.items:
		if item.item_code == item_code:
			# Set the IGST Rate and IGST Amount
			item.igst_rate = igst_rate
			item.igst_amount = igst_amount
			break

def zero_igst(self):
	for item in self.items:
		item.igst_rate = 0
		item.igst_amount = 0