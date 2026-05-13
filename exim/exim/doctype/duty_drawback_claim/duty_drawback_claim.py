# Copyright (c) 2023, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
# import datetime
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions
)

def apply_accounting_dimensions(source_doc, target_row):
		for dim in get_accounting_dimensions():
			if source_doc.get(dim):
				target_row[dim] = source_doc.get(dim)


class DutyDrawBackClaim(Document):
	def validate(self):
		total = 0.0
		total1=0.0
		for row in self.rodtep_details:
			total = total + row.debit_amount
			total1=total1+row.received_amount
		self.total_debit_amount = total
		self.script_amount=total1
		self.round_off_amount=flt(total)-flt(total1)
		if self.round_off_amount >= round(flt(20,2)):
			frappe.throw("round of ammount should be less than 20")

		dimensions = get_accounting_dimensions()

		for row in self.rodtep_details:

			if not row.cheque_no:
				continue

			si = frappe.get_doc("Sales Invoice", row.cheque_no)

			for dim in dimensions:
				row_val = row.get(dim)
				si_val = si.get(dim)

				if row_val and row_val != si_val:
					frappe.throw(
						f"""
						<b>Row {row.idx}</b>
						Invalid value for Accounting Dimencian<b>{row_val}</b><br>
						Allowed: <b>{si_val}</b>
						"""
					)
		
	def on_submit(self):
		total_debit_amount = (
			flt(self.total_debit_amount) - flt(self.round_off_amount)
		)

		self.db_set("total_debit_amount", total_debit_amount)

		if round(flt(total_debit_amount), 4) != round(flt(self.script_amount), 4):
			frappe.throw("""Total Script Amount and Total Debit Amount should be equal """)

		if not self.credit_account:
			frappe.throw("""Set credit account first""")

	def on_cancel(self):
		if self.journal_entry_ref:
			jv = frappe.get_doc("Journal Entry", self.journal_entry_ref)
			jv.cancel()
			self.db_set("journal_entry_ref", "")

def exp_je_data(company):

	list_of_je = frappe.db.sql(
		"""
		SELECT
			rcm.je_no,
			rd.journal_entry_ref

		FROM `tabDrawback Details` AS rcm

		JOIN `tabDuty DrawBack Claim` AS rd

		WHERE
			rd.company = %s
			AND rd.docstatus != 2
		""",
		(company,),
		as_list=True
	)

	je = []

	for row in list_of_je:
		for d in row:
			je.append(str(d))

	return je


@frappe.whitelist()
def journal_entry_list(start_date, end_date, company):

	list_of_je = exp_je_data(company)

	args = {
		"r_start_date": start_date,
		"r_end_date": end_date,
		"company": company
	}

	conditions = ""

	if list_of_je:
		placeholders = ", ".join(["%s"] * len(list_of_je))
		conditions = f" AND je.name NOT IN ({placeholders})"

	query = f"""
		SELECT
			je.name AS je_no,
			jea.debit_in_account_currency AS debit_amount,
			je.cheque_date,
			je.cheque_no,
			si.shipping_bill_number AS shipping_bill_no,
			c.duty_drawback_receivable_account AS account

		FROM `tabJournal Entry` AS je

		LEFT JOIN `tabJournal Entry Account` AS jea
			ON jea.parent = je.name

		LEFT JOIN `tabSales Invoice` AS si
			ON si.name = je.cheque_no

		LEFT JOIN `tabCompany` AS c
			ON c.name = je.company

		WHERE
			je.voucher_type = 'Duty Drawback Entry'
			AND je.posting_date >= %(r_start_date)s
			AND je.posting_date <= %(r_end_date)s
			AND jea.debit_in_account_currency > 0
			AND je.docstatus < 2
			AND je.company = %(company)s
			{conditions}
	"""

	values = args

	if list_of_je:
		values = tuple(args.values()) + tuple(list_of_je)

	je_data = frappe.db.sql(
		query,
		values,
		as_dict=1
	)

	return je_data

def create_jv_on_submit(self,method):
	if(round(flt(self.total_debit_amount),4) == round(flt(self.script_amount),4)):
		meis_receivable_account = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_receivable_account")
		meis_income_account = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_income_account")
		meis_cost_center = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_cost_center")
		
		if not meis_receivable_account:
			frappe.throw(_("Set Duty Drawback Receivable Account in Company"))
		elif not meis_income_account:
			frappe.throw(_("Set Duty Drawback Income Account in Company"))
		elif not meis_cost_center:
			frappe.throw(_("Set Duty Drawback Cost Center in Company"))
		else:
			meis_jv = frappe.new_doc("Journal Entry")
			meis_jv.voucher_type = "Duty Drawback Entry"
			meis_jv.posting_date = self.posting_date
			meis_jv.company = self.company
			meis_jv.cheque_no = self.name
			meis_jv.cheque_date = self.posting_date
			meis_jv.user_remark = "Duty Drawback against " + self.name 
			for row in self.rodtep_details:
				acc_row = {
					"account": row.account,
					"reference_type": "Journal Entry",
					"reference_name": row.je_no,
					"credit_in_account_currency": row.debit_amount,
				}
				apply_accounting_dimensions(row, acc_row)
				meis_jv.append("accounts", acc_row)

			debit_row = {
				"account": self.credit_account,
				"debit_in_account_currency":self.total_debit_amount,
			}
			apply_accounting_dimensions(row, debit_row)
			meis_jv.append("accounts", debit_row)

			if self.round_off_amount < 0.0:
				round_row = {
					"account": self.round_off_account,
					"credit_in_account_currency":-flt(self.round_off_amount),
				}
				apply_accounting_dimensions(row, round_row)
				meis_jv.append("accounts", round_row)
			elif self.round_off_amount > 0.0:
				round_grater_row = {
					"account": self.round_off_account,
					"debit_in_account_currency":flt(self.round_off_amount),
				}
				apply_accounting_dimensions(row, round_grater_row)
				meis_jv.append("accounts", round_grater_row)
			try:
				meis_jv.save(ignore_permissions=True)
				meis_jv.submit()
				self.db_set('journal_entry_ref',meis_jv.name)
				if meis_jv.name:
					frappe.msgprint("Journal Entry Created Successfully {}".format(frappe.bold(meis_jv.name)))
			except Exception as e:
				frappe.throw(str(e))
	
	

