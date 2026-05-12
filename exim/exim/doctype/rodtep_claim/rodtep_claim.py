# Copyright (c) 2023, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
from frappe import _
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions
)


def apply_accounting_dimensions(source_doc, target_row):
		for dim in get_accounting_dimensions():
			if source_doc.get(dim):
				target_row[dim] = source_doc.get(dim)

# import datetime
from frappe.utils import flt
class RodtepClaim(Document):
	def validate(self):
		total = 0.0
		for row in self.rodtep_details:
			total = total + row.debit_amount
		self.total_debit_amount = total
		self.script_amount=total

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
		if(round(flt(self.total_debit_amount),4) != round(flt(self.script_amount),4)):
			frappe.throw(f"""Total Script Amount and Total Debit Amount should be equal """)
		
		if not self.credit_account:
			frappe.throw(f"""Set credit account first""")

	def on_cancel(self):
		if self.journal_entry_ref:
			jv = frappe.get_doc("Journal Entry", self.journal_entry_ref)
			jv.cancel()
			self.journal_entry_ref = ''

def exp_je_data(company):

	list_of_je = frappe.db.sql(
		"""
		SELECT
			rcm.je_no,
			rd.journal_entry_ref

		FROM `tabRodtep Details` AS rcm

		JOIN `tabRodtep Claim` AS rd

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

	args = [
		start_date,
		end_date,
		company
	]

	conditions = ""

	if list_of_je:
		placeholders = ", ".join(["%s"] * len(list_of_je))
		conditions = f" AND je.name NOT IN ({placeholders})"
		args.extend(list_of_je)

	query = f"""
		SELECT
			je.name AS je_no,
			jea.debit_in_account_currency AS debit_amount,
			je.cheque_date,
			je.cheque_no,
			si.shipping_bill_number AS shipping_bill_no,
			c.meis_receivable_account AS account,
			je.company

		FROM `tabJournal Entry` AS je

		LEFT JOIN `tabJournal Entry Account` AS jea
			ON jea.parent = je.name

		LEFT JOIN `tabSales Invoice` AS si
			ON si.name = je.cheque_no

		LEFT JOIN `tabCompany` AS c
			ON c.name = je.company

		WHERE
			je.voucher_type = 'RODTEP Entry'
			AND je.posting_date >= %s
			AND je.posting_date <= %s
			AND jea.debit_in_account_currency > 0
			AND je.docstatus < 2
			AND je.company = %s
			{conditions}
	"""

	je_data = frappe.db.sql(
		query,
		tuple(args),
		as_dict=1
	)

	return je_data

def create_jv_on_submit(self,method):
	if(round(flt(self.total_debit_amount),4) == round(flt(self.script_amount),4)):
		meis_receivable_account = frappe.db.get_value("Company", { "company_name": self.company}, "meis_receivable_account")
		meis_income_account = frappe.db.get_value("Company", { "company_name": self.company}, "meis_income_account")
		meis_cost_center = frappe.db.get_value("Company", { "company_name": self.company}, "meis_cost_center")
		if not meis_receivable_account:
			frappe.throw(_("Set RODTEP Receivable Account in Company"))
		elif not meis_income_account:
			frappe.throw(_("Set RODTEP Income Account in Company"))
		elif not meis_cost_center:
			frappe.throw(_("Set RODTEP Cost Center in Company"))
		else:
			meis_jv = frappe.new_doc("Journal Entry")
			meis_jv.voucher_type = "RODTEP Entry"
			meis_jv.posting_date = self.posting_date
			meis_jv.company = self.company
			meis_jv.cheque_no = self.name
			meis_jv.cheque_date = self.posting_date
			meis_jv.user_remark = "RODTEP against " + self.name 
			use_dimensions = frappe.db.get_single_value(
				"Exim Settings",
				"manage_rodtep_claim_and_duty_drawback_claim"
			)
			if use_dimensions:
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
			else:
				for row in self.rodtep_details:
					meis_jv.append("accounts", {
						"account": row.account,
						"reference_type": "Journal Entry",
						"reference_name": row.je_no,
						"credit_in_account_currency":row.debit_amount,
					})
				meis_jv.append("accounts", {
					"account": self.credit_account,
					"debit_in_account_currency":self.total_debit_amount,
				})
			
			try:
				meis_jv.save(ignore_permissions=True)
				meis_jv.submit()
				self.db_set('journal_entry_ref',meis_jv.name)
				if meis_jv.name:
					frappe.msgprint("Journal Entry Created Successfully {}".format(frappe.bold(meis_jv.name)))
			except Exception as e:
				frappe.throw(str(e))
				
