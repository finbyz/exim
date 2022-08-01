# -*- coding: utf-8 -*-
# Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, cint, add_months, add_days, get_url_to_form
from erpnext.setup.utils import get_exchange_rate

class PreShipment(Document):
	def validate(self):
		self.loan_due_date = add_days(self.posting_date, cint(self.loan_tenure))

		self.validate_document_field()
		if self.docstatus == 0:
			self.validate_loan_amount()

		self.calculate_forward_utilization()
		self.set_exchange_rate()
		self.calculate_loan_amount()
		self.calculate_repayments()

		if self._action == 'submit':
			self.validate_fields()

	def calculate_forward_utilization(self):
		if self.get('forwards'):
			self.total_amount_utilized = sum([row.amount_utilized for row in self.get('forwards')])
			self.average_forward_rate = sum([(flt(row.forward_rate) * flt(row.amount_utilized)) for row in self.get('forwards')])/flt(self.total_amount_utilized)
			self.cash_amount = flt(self.loan_amount) - flt(self.total_amount_utilized)
			
			amount_utilized = (flt(self.total_amount_utilized) + flt(self.cash_amount)) - flt(self.loan_amount)
			if amount_utilized != 0:
				frappe.throw(_("The sum of Total Amount Utilized and Cash Amount must be same as Loan Amount."))

	def validate_document_field(self):
		if not cint(self.running) and not self.document:
			frappe.throw(_("Please select the document if Pre Shipment is not running or else tick 'Running'."))

	def set_exchange_rate(self):
		if not self.cash_rate:
			self.cash_rate = get_exchange_rate(self.credit_currency, "INR", self.posting_date)

		total_utilization = flt(self.total_amount_utilized) + flt(self.cash_amount)
		if total_utilization > 0:
			weighted_average_rate = ((flt(self.average_forward_rate) * flt(self.total_amount_utilized)) + (flt(self.cash_rate) * flt(self.cash_amount))) / total_utilization

			if weighted_average_rate:
				self.source_exchange_rate = weighted_average_rate
			
		elif self.credit_currency and not self.source_exchange_rate:
			self.source_exchange_rate = get_exchange_rate(self.credit_currency, "INR", self.posting_date)

	def validate_loan_amount(self):
		if not cint(self.running) and flt(self.loan_amount) > flt(self.total_amount):
			frappe.throw(_("Loan Amount cannot be greater that Total Amount."))

	def calculate_loan_amount(self):
		self.loan_amount_inr = flt(self.source_exchange_rate * self.loan_amount)
		self.loan_outstanding_amount_inr = flt(self.source_exchange_rate * self.loan_outstanding_amount)

	@frappe.whitelist()
	def get_document_details(self):
		out = frappe._dict()

		if self.against == "Contract Term":
			values = frappe.db.get_value(self.against, self.document, ['currency', 'contract_amount'], as_dict=1)
			out.underline_currency = values.currency
			out.total_amount = flt(values.contract_amount)
			out.total_amount_inr = flt(self.source_exchange_rate * values.contract_amount)

		else:
			values = frappe.db.get_value(self.against, self.document, ['currency', 'total', 'base_total'], as_dict=1)
			out.underline_currency = values.currency
			out.total_amount = flt(values.total)
			out.total_amount_inr = flt(values.base_total)

		return out

	def validate_fields(self):
		if not self.loan_account:
			frappe.throw(_("Please set Loan Account"))

		elif not self.loan_credit_account:
			frappe.throw(_("Please set Loan Credit Account"))

		elif not self.bank_loan_reference:
			frappe.throw(_("Please set Bank Loan Reference"))

	def on_update(self):
		self.update_status()

	def on_submit(self):
		self.update_documents()
		self.update_status()
		if(self.cash_amount < 0):
			frappe.throw(_("Cash Amount can not be less then zero."))


	def on_cancel(self):
		self.cancel_jv()
		self.update_forward()

	def update_documents(self):
		self.update_forward()
		self.create_jv()

	def update_status(self):
		status = ''

		if self.docstatus == 0:
			status = "Draft"
		else:
			if self.loan_outstanding_amount == self.loan_amount:
				status = "Outstanding"
			elif self.loan_outstanding_amount == 0.0:
				status = "Paid"
			elif self.loan_outstanding_amount < self.loan_amount:
				status = "Partially Paid"

		self.db_set('status', status)

	def create_jv(self):
		jv = frappe.new_doc("Journal Entry")
		
		jv.voucher_type = "Bank Entry"
		jv.posting_date = self.posting_date
		jv.company = self.company

		loan_amount = self.loan_amount_inr

		if self.credit_currency != "INR":
			jv.multi_currency = 1
			loan_amount = self.loan_amount

		jv.append('accounts', {
			'account': self.loan_account,
			'account_currency': self.credit_currency,
			'exchange_rate': self.source_exchange_rate,
			'credit_in_account_currency': loan_amount,
			'credit': self.loan_amount_inr,
		})

		jv.append('accounts', {
			'account': self.loan_credit_account,
			'exchange_rate': self.source_exchange_rate,
			'debit_in_account_currency': self.loan_amount_inr,
			'debit': self.loan_amount_inr,
		})

		jv.cheque_no = self.bank_loan_reference
		jv.cheque_date = self.posting_date
		if cint(self.running):
			remarks = "PCFC taken as running account"
		else:
			remarks = "PCFC against " + self.against + " : " + self.document

		jv.user_remark = remarks
		jv.credit_days = cint(self.loan_tenure)
		jv.bill_no = self.bank_loan_reference
		jv.bill_date = self.posting_date
		jv.due_date = self.loan_due_date

		try:
			jv.save()
			jv.submit()
		except Exception as e:
			frappe.throw(_(e))

		self.journal_entry = jv.name
		self.db_update()

		url = get_url_to_form("Journal Entry", jv.name)
		frappe.msgprint(_("Journal Entry - <a href='{url}'>{doc}</a> has been created.".format(url=url, doc=frappe.bold(jv.name))))

	def cancel_jv(self):
		if self.journal_entry:
			jv = frappe.get_doc("Journal Entry", self.journal_entry)
			jv.cancel()
			self.journal_entry = ''
			self.db_update()
			url = get_url_to_form("Journal Entry", jv.name)
			frappe.msgprint(_("Journal Entry - <a href='{url}'>{doc}</a> has been cancelled.".format(url=url, doc=frappe.bold(jv.name))))

	def update_forward(self):
		if self._action == 'submit':
			customer_field = 'customer'
			if self.against == 'Contract Term':
				customer_field = 'applicant'
			
			party = frappe.db.get_value(self.against, self.document, customer_field)

			for row in self.get('forwards'):
				doc = frappe.get_doc("Forward Booking", row.forward_contract)

				if not frappe.db.get_value("Forward Booking Utilization", filters={"parent": row.forward_contract, "voucher_type": "Pre Shipment", "voucher_no": self.name}):
					doc.append("payment_entries", {
						"date": self.posting_date,
						"party_type": "Customer",
						"party": party,
						"paid_amount" : row.amount_utilized,
						"voucher_type": "Pre Shipment",
						"voucher_no" : self.name,
					})
				doc.save()
			
		elif self._action == 'cancel':
			for row in self.get('forwards'):
				doc = frappe.get_doc("Forward Booking", row.forward_contract)
				to_remove = [row for row in doc.payment_entries if row.voucher_no == self.name and row.voucher_type == "Pre Shipment"]
				[doc.remove(row) for row in to_remove]
				doc.save()
			

	def before_update_after_submit(self):
		self.validate_document_field()

	def on_update_after_submit(self):
		self.calculate_repayments()
		self.update_status()
		self.db_update()

	def calculate_repayments(self):
		self.total_repayment = sum([row.amount for row in self.get('repayments')])
		self.total_repayment_inr = sum([row.amount_inr for row in self.get('repayments')])

		loan_outstanding_amount	= flt(self.loan_amount) - flt(self.total_repayment)

		if loan_outstanding_amount < 0:
			frappe.throw(_("Loan Outstanding Amount is becoming negaive with value {}".format(loan_outstanding_amount)))

		self.loan_outstanding_amount = loan_outstanding_amount
		self.loan_outstanding_amount_inr = flt(self.loan_amount_inr) - flt(self.total_repayment_inr)