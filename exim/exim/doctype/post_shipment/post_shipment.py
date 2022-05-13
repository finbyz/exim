# -*- coding: utf-8 -*-
# Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, add_days, cint, get_url_to_form
from erpnext.setup.utils import get_exchange_rate

class PostShipment(Document):
	def validate(self):
		self.loan_due_date = add_days(self.posting_date, cint(self.loan_tenure))

		self.validate_loan_amount()
		self.calculate_repayments()
		self.calculate_forward_utilization()
		self.set_exchange_rate()
		self.calculate_loan_amount()

		if self._action == 'submit':
			self.validate_fields()

	def validate_loan_amount(self):
		if self.loan_amount > self.total_amount:
			frappe.throw(_("Loan Amount cannot be greater that Total Amount"))

		self.loan_amount_inr = flt(self.source_exchange_rate * self.loan_amount)

	def calculate_repayments(self):
		total_outstanding_amount = 0
		total_outstanding_amount_inr = 0
		total_repayment_amount = 0
		total_repayment_amount_inr = 0

		for row in self.get('repayments'):
			if row.repayment_amount > row.outstanding_amount:
				frappe.throw(_("Repayment Amount should not be greater than Outstanding Amount in Row # {}".format(row.idx)))

			total_outstanding_amount += row.outstanding_amount
			total_outstanding_amount_inr += row.outstanding_amount_inr
			total_repayment_amount += row.repayment_amount
			total_repayment_amount_inr += row.repayment_amount_inr

		if total_repayment_amount > self.loan_amount:
			frappe.throw(_("Total Repayment cannot be greater that loan amount"))
			return

		self.total_outstanding_amount = total_outstanding_amount
		self.total_outstanding_amount_inr = total_outstanding_amount_inr
		self.total_repayment_amount = total_repayment_amount
		self.total_repayment_amount_inr = total_repayment_amount_inr

	def calculate_forward_utilization(self):
		self.average_forward_rate = sum([row.forward_rate for row in self.get('forwards')])
		self.total_amount_utilized = sum([row.amount_utilized for row in self.get('forwards')])
		cash_amount = flt(self.loan_amount) - flt(self.total_amount_utilized) - flt(self.total_repayment_amount)

		if cash_amount < 0:
			frappe.throw(_("Plase check Forwarad Utilization or Repayment Table. The loan amount - sum of total amount utilized and total repayment amount must be greater than 0."))
		else:
			self.cash_amount = cash_amount

		amount_utilized = (flt(self.total_amount_utilized) + flt(self.cash_amount) + flt(self.total_repayment_amount)) - flt(self.loan_amount)
		if amount_utilized != 0:
			frappe.throw(_("The sum of Total Amount Utilized, Cash Amount and Repayment Amount must be same as Loan Amount."))

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

	def calculate_loan_amount(self):
		self.loan_amount_inr = self.source_exchange_rate * self.loan_amount
		self.loan_outstanding_amount = self.loan_amount
		self.loan_outstanding_amount_inr = self.source_exchange_rate * self.loan_outstanding_amount

	@frappe.whitelist()
	def get_document_details(self):
		out = frappe._dict()

		if self.against == "Contract Term":
			values = frappe.db.get_value(self.against, self.document, ['currency', 'contract_amount', 'applicant'], as_dict=1)
			out.underline_currency = values.currency
			out.total_amount = flt(values.contract_amount)
			out.total_amount_inr = flt(self.source_exchange_rate * values.contract_amount)
			out.party = values.applicant

		else:
			values = frappe.db.get_value(self.against, self.document, ['currency', 'total', 'base_total', 'customer'], as_dict=1)
			out.underline_currency = values.currency
			out.total_amount = flt(values.total)
			out.total_amount_inr = flt(values.base_total)
			out.party = values.customer

		return out

	def on_submit(self):
		self.create_jv()
		self.update_forward()
		self.update_pre_shipment()

	def on_cancel(self):
		self.cancel_jv()
		self.update_forward()
		self.update_pre_shipment()

	def validate_fields(self):
		if not self.loan_account:
			frappe.throw(_("Please set Loan Account"))

		elif not self.loan_credit_account:
			frappe.throw(_("Please set Loan Credit Account"))

		elif not self.bank_loan_reference:
			frappe.throw(_("Please set Bank Loan Reference"))

	def create_jv(self):
		jv = frappe.new_doc("Journal Entry")
		
		jv.voucher_type = "Bank Entry"
		jv.posting_date = self.posting_date
		jv.company = self.company
		jv.multi_currency = 1

		if self.credit_currency == "INR":
			jv.multi_currency = 0

		repayment_amount = 0

		for d in self.get('repayments'):
			jv.append('accounts', {
				'account': self.loan_account,
				'account_currency': self.credit_currency,
				'exchange_rate': d.exchange_rate,
				'credit_in_account_currency': d.repayment_amount,
				'credit': d.repayment_amount_inr,
			})

			jv.append('accounts', {
				'account': d.loan_account,
				'account_currency': d.currency,
				'exchange_rate': d.exchange_rate,
				'debit_in_account_currency': d.repayment_amount,
				'debit': d.repayment_amount_inr,
			})

			repayment_amount += d.repayment_amount

		diff_amount = self.loan_amount - self.total_repayment_amount

		if diff_amount > 0:
			diff_amount_inr = flt(self.source_exchange_rate) * flt(diff_amount)
			
			jv.append('accounts', {
				'account': self.loan_account,
				'account_currency': self.credit_currency,
				'exchange_rate': self.source_exchange_rate,
				'credit_in_account_currency': diff_amount,
				'credit': diff_amount_inr,
			})

			jv.append('accounts', {
				'account': self.loan_credit_account,
				'account_currency': "INR",
				'exchange_rate': 1,
				'debit_in_account_currency': diff_amount_inr,
				'debit': diff_amount_inr,
			})

		jv.cheque_no = self.bank_loan_reference
		jv.cheque_date = self.posting_date
		jv.user_remark = "Post Shipment against " + self.against + " : " + self.document
		jv.credit_days = cint(self.loan_tenure)
		jv.bill_no = self.bank_loan_reference
		jv.bill_date = self.posting_date
		jv.due_date = self.loan_due_date

		jv.save()
		jv.submit()

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
			for row in self.get('forwards'):
				doc = frappe.get_doc("Forward Booking", row.forward_contract)

				if not frappe.db.get_value("Forward Booking Utilization", filters={"parent": row.forward_contract, "voucher_type": "Post Shipment", "voucher_no": self.name}):
					doc.append("payment_entries", {
						"date": self.posting_date,
						"party_type": "Customer",
						"party": self.party,
						"paid_amount" : self.loan_amount,
						"voucher_type": "Post Shipment",
						"voucher_no" : self.name,
					})
				doc.save()
			

		elif self._action == 'cancel':
			for row in self.get('forwards'):
				doc = frappe.get_doc("Forward Booking", row.forward_contract)
				to_remove = [row for row in doc.payment_entries if row.voucher_no == self.name and row.voucher_type == "Post Shipment"]
				[doc.remove(row) for row in to_remove]
				doc.save()

	def update_pre_shipment(self):
		if self._action == 'submit':
			for row in self.get('repayments'):
				doc = frappe.get_doc("Pre Shipment", row.pre_shipment)

				if not frappe.db.get_value("Pre Shipment Repayment", filters={"parent": row.pre_shipment, "voucher_type": "Post Shipment", "voucher_no": self.name}):
					doc.append("repayments", {
						"amount": row.repayment_amount,
						"amount_inr": row.repayment_amount_inr,
						"voucher_type": "Post Shipment",
						"voucher_no" : self.name,
					})
				doc.save()
			
		elif self._action == 'cancel':
			for row in self.get('repayments'):
				doc = frappe.get_doc("Pre Shipment", row.pre_shipment)
				to_remove = [row for row in doc.repayments if row.voucher_no == self.name and row.voucher_type == "Post Shipment"]
				[doc.remove(row) for row in to_remove]
				doc.save()
			