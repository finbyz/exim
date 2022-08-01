# -*- coding: utf-8 -*-
# Copyright (c) 2018, Finbyz Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, date_diff, nowdate, get_url_to_form
from datetime import datetime


class ForwardBooking(Document):
	def on_submit(self):
		self.calculate_underlying()

	def on_cancel(self):
		self.calculate_underlying()

	def validate(self):
		self.calculate_forward_limit()
		self.calculate_cancellation()
		self.set_status()
		# self.calculate_days_of_premium()
		if self.docstatus != 0:
			self.db_update()
			
	def calculate_underlying(self):
		for row in self.forward_booking_underlying:
			doc = frappe.get_doc(row.link_to, row.document)
			if self._action == 'submit':
				amount_hedged = flt(doc.amount_hedged) + flt(row.amount_covered)
			elif self._action == 'cancel':
				amount_hedged = flt(doc.amount_hedged) - flt(row.amount_covered)

			amount_unhedged = flt(doc.grand_total) - flt(amount_hedged) - flt(doc.advance_paid) - flt(doc.natural_hedge)
			doc.amount_hedged = flt(amount_hedged)
			doc.amount_unhedged = flt(amount_unhedged)
			doc.save()
		

		self.db_set('total_underlying', sum([flt(row.amount_covered) for row in self.forward_booking_underlying]))

	def calculate_forward_limit(self):
		self.booking_rate = flt(self.current_rate) + flt(self.premium) - flt(self.margin)
		self.days_for_limit_blocked = date_diff(self.maturity_to, self.booking_date)
		self.outstanding_inr = flt(self.amount) * flt(self.booking_rate)

		if self.days_for_limit_blocked <= 30:
			self.margin_percentage = 4.5
		elif self.days_for_limit_blocked <= 60:
			self.margin_percentage = 7.6
		elif self.days_for_limit_blocked <= 90:
			self.margin_percentage = 8.78
		elif self.days_for_limit_blocked <= 150:
			self.margin_percentage = 10.19

		self.forward_limit_inr = (flt(self.outstanding_inr) * flt(self.margin_percentage)) / 100.0
		self.forward_limit_usd = flt(self.forward_limit_inr) / flt(self.booking_rate)
		self.forward_limit_inr_mtm = ((flt(self.forward_limit_constant) - flt(self.current_rate)) * flt(self.amount)) + flt(self.forward_limit_inr)

	def calculate_days_of_premium(self):
		if self.hedge == "Export":
			if self.maturity_from:
				days_for_premium = datetime.strptime(self.maturity_from, "%Y-%m-%d") - datetime.strptime(self.booking_date, "%Y-%m-%d")
				days_for_premium = str(days_for_premium)
				days_for_premium = days_for_premium.split(' ')[0]
				self.days_for_premium = days_for_premium
			else:
				days_for_premium = datetime.strptime(self.maturity_to, "%Y-%m-%d") - datetime.strptime(self.booking_date, "%Y-%m-%d")
				days_for_premium = str(days_for_premium)
				days_for_premium = days_for_premium.split(' ')[0]
				self.days_for_premium = days_for_premium
		elif self.hedge == "Import":
			days_for_premium = datetime.strptime(self.maturity_to, "%Y-%m-%d") - datetime.strptime(self.booking_date, "%Y-%m-%d")
			days_for_premium = str(days_for_premium)
			days_for_premium = days_for_premium.split(' ')[0]
			self.days_for_premium = days_for_premium

	@frappe.whitelist()
	def add_cancellation_details(self):
		self.validate_cancellation_fields()
		self.add_cancellation()
		self.submit()

	def add_cancellation(self):
		if self.hedge == "Export":
			rate_diff = flt(self.booking_rate) - flt(self.cancellation_rate)
		else:
			rate_diff = flt(self.cancellation_rate) - flt(self.booking_rate)

		row = frappe._dict({
			'date': self.cancellation_date,
			'rate': self.cancellation_rate,
			'cancel_amount': self.cancellation_amount,
			'inr_amount': flt(self.cancellation_rate) * flt(self.cancellation_amount),
			'rate_diff': flt(rate_diff),
			'profit_or_loss': flt(rate_diff) * flt(self.cancellation_amount),
			'bank_account': self.bank_account,
		})
		if abs(row.get('profit_or_loss')):
			self.create_row_jv(row)
		else:
			frappe.msgprint("Journal Entry was not created because there is no profit or loss")
		self.append('cancellation_details', row)

		self.cancellation_date = ''
		self.cancellation_rate = 0.0
		self.cancellation_amount = 0.0
		self.bank_account = ''

	def validate_cancellation_fields(self):
		if not self.cancellation_date:
			frappe.throw(_("Please add cancellation date."))

		if not self.cancellation_rate:
			frappe.throw(_("Please add cancellation rate."))

		if not self.cancellation_amount:
			frappe.throw(_("Please add cancellation amount."))

		if not self.bank_account:
			frappe.throw(_("Please add bank account."))

	def create_jv(self, row):
		doc = ''
		for d in self.cancellation_details:
			if d.name == row:
				doc = d
				break

		if not doc.bank_account:
			frappe.throw(_("Please add bank account in row: {}".format(doc.idx)))

		if self.hedge == "Export":
			rate_diff = flt(self.booking_rate) - flt(doc.rate)
		else:
			rate_diff = flt(doc.rate) - flt(self.booking_rate)
		
		doc.rate_diff = flt(rate_diff)
		doc.profit_or_loss = flt(rate_diff) * flt(doc.cancel_amount)
		doc.db_update()

		self.create_row_jv(doc)
		self.submit()
		
	@frappe.whitelist()
	def cancel_jv(self, row):
		to_remove = []

		for d in self.cancellation_details:
			if d.name == row and d.journal_entry:
				jv = frappe.get_doc("Journal Entry", d.journal_entry)
				d.journal_entry = ''
				d.db_update()
				jv.cancel()
				url = get_url_to_form("Journal Entry", jv.name)
				frappe.msgprint(_("Journal Entry - <a href='{url}'>{doc}</a> has been cancelled.".format(url=url, doc=frappe.bold(jv.name))))

				to_remove.append(d)

		[self.remove(d) for d in to_remove]
		self.calculate_cancellation()
		self.set_status()
		self.db_update()
		self.submit()

	def create_row_jv(self, row):
		jv = frappe.new_doc("Journal Entry")
		jv.voucher_type = "Journal Entry"
		jv.naming_series = "JV-.fiscal.-"
		jv.posting_date = self.maturity_to
		
		if not self.company:
			self.db_set('company', frappe.defaults.get_global_default('company'))

		jv.company = self.company

		exchange_gain_loss_account = frappe.db.get_value("Company", self.company, 'exchange_gain_loss_account')

		if row.profit_or_loss > 0:
			credit_account = exchange_gain_loss_account
			debit_account = row.bank_account

		else:
			credit_account = row.bank_account
			debit_account = exchange_gain_loss_account

		pnl_amount = abs(row.profit_or_loss)

		jv.append('accounts', {
			'account': credit_account,
			'credit_in_account_currency': pnl_amount,
		})

		jv.append('accounts', {
			'account': debit_account,
			'debit_in_account_currency': pnl_amount
		})

		jv.cheque_no = self.name
		jv.cheque_date = row.date

		try:
			jv.save()
		except Exception as e:
			frappe.throw(_(str(e)))
		else:
			jv.submit()
			row.journal_entry = jv.name
			url = get_url_to_form("Journal Entry", jv.name)
			frappe.msgprint(_("Journal Entry - <a href='{url}'>{doc}</a> has been created.".format(url=url, doc=frappe.bold(jv.name))))

	def on_update_after_submit(self):
		self.calculate_total_utilization()
		self.calculate_cancellation()
		self.set_status()
		self.db_update()

	def calculate_total_utilization(self):
		self.total_utilization = sum([flt(row.paid_amount) for row in self.get('payment_entries')])

	def calculate_cancellation(self):
		total_inr_amount = sum([flt(d.inr_amount) for d in self.cancellation_details])
		total_cancel_amount = sum([flt(d.cancel_amount) for d in self.cancellation_details])

		if total_cancel_amount:
			self.total_cancelled = total_cancel_amount
			self.can_avg_rate = flt(total_inr_amount) / flt(total_cancel_amount)

			if self.hedge == "Export":
				self.rate_diff = flt(self.booking_rate) - flt(self.can_avg_rate)
			else:
				self.rate_diff = flt(self.can_avg_rate) - flt(self.booking_rate)

			self.diff_amount = flt(self.rate_diff) * flt(self.total_cancelled)
	
	def set_status(self):
		self.amount_outstanding = flt(self.amount) - flt(self.total_utilization) - flt(self.total_cancelled)
		
		if self.amount_outstanding < 0.0:
			frappe.throw(_("Amount Outstanding is becoming negative for forward contract %s." % self.name))
			validated = False

		if self.amount_outstanding == 0.0:
			self.status = "Closed"
		else:
			self.status = "Open"
