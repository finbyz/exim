# Copyright (c) 2022, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class BRCManagement(Document):
	def validate(self):
		self.cal_total()
		if self.total_shipping_bill_amount > self.base_rounded_total:
			frappe.throw("Total Shipping Bill Amount should not be greater than Invoice Amount")

		for item in self.brc_payment:
			if item.brc_amount > item.total_allocated_amount:
				frappe.throw(f"""Row {item.idx}: BRC Amount should not be greater than Total Allocate Amount """)
			
		if self.total_payment_receipt > self.total_shipping_bill_amount:
			frappe.throw(f"""Total Receipt Amount should not be greater than Total Shipping bill Amount """)

	def on_update(self):
		self.update_status()
	
	def on_submit(self):
		self.update_status()

	def on_update_after_submit(self):
		self.update_status()

		if self.total_payment_receipt > self.total_shipping_bill_amount:
			frappe.throw(f"""Total Receipt Amount should not be greater than Total Shipping bill Amount """)
			
		for item in self.brc_payment:
			if item.brc_amount > item.total_allocated_amount:
				frappe.throw(f"""Row {item.idx}: BRC Amount should not be greater than Total Allocate Amount """)
		
		if not self.brc_payment:
			self.total_brc_amount = 0
			self.total_payment_receipt = 0

	def cal_total(self):
		total_shipping_bill_amount = 0.0
		total_brc_amount = 0.0
		total_payment_receipt = 0.0
		total_bank_charges = 0.0 

		for item in self.shipping_bill_details:
			total_shipping_bill_amount += flt(item.shipping_bill_amount)

		for item in self.brc_payment:
			total_brc_amount += flt(item.brc_amount)
			total_payment_receipt += flt(item.total_allocated_amount)
			item.bank_charges =  item.total_allocated_amount - item.brc_amount

		self.total_shipping_bill_amount = total_shipping_bill_amount
		self.total_brc_amount = total_brc_amount
		self.total_payment_receipt = total_payment_receipt

	def update_status(self):
		status = ''
		
		if not self.total_shipping_bill_amount:
			status = "Open"
		elif self.total_brc_amount == 0 :
			status = "Open"
		elif self.total_bank_charges + self.total_brc_amount < self.total_shipping_bill_amount:
			status = "Partially BRC Generated"
		elif not self.brc_payment:
			status = "Partially BRC Generated"
		elif self.total_bank_charges + self.total_brc_amount == self.total_shipping_bill_amount:
			status = "Completed"
			
		self.db_set('status', status)