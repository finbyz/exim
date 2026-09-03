# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
# Copyright (c) 2023, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions
)

def apply_accounting_dimensions(source_doc, target_row):
		for dim in get_accounting_dimensions():
			if source_doc.get(dim):
				target_row[dim] = source_doc.get(dim)


class IGSTRefundClaim(Document):
	def validate(self):
		total = 0.0
		total1=0.0
		for row in self.igst_refund_details:
			total = total + row.debit_amount
			total1=total1+row.received_amount
		self.total_debit_amount = total
		self.script_amount=total1
		self.round_off_amount=flt(total)-flt(total1)
		if self.round_off_amount >= round(flt(20,2)):
			frappe.throw("round of ammount should be less than 20")

		dimensions = get_accounting_dimensions()

		for row in self.igst_refund_details:

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
						Invalid value for Accounting Dimension<b>{row_val}</b><br>
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
   
		self.update_igst_received()
  

		
  
	def on_cancel(self):
		if self.journal_entry_ref:
			jv = frappe.get_doc("Journal Entry", self.journal_entry_ref)
			jv.cancel()
			self.db_set("journal_entry_ref", "")
			self.reset_igst_received()
   
	def reset_igst_received(self):
		for row in self.igst_refund_details:
			if row.cheque_no:
				si = frappe.get_doc("Sales Invoice", row.cheque_no)
				si.db_set("igst_received", 0)
   
	def update_igst_received(self):
		for row in self.igst_refund_details:
			if row.cheque_no:
				si = frappe.get_doc("Sales Invoice", row.cheque_no)
				si.db_set("igst_received", 1)
    
    

def exp_je_data(company):
	
	list_of_je = frappe.db.sql(
		"""
		SELECT
			rcm.je_no,
			rd.journal_entry_ref

		FROM `tabIGST Refund Details` AS rcm

		JOIN `tabIGST Refund Claim` AS rd

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

	values = {
		"r_start_date": start_date,
		"r_end_date": end_date,
		"company": company,
	}

	query = """
		SELECT
			je.name AS je_no,
			jea.debit_in_account_currency AS debit_amount,
			je.cheque_date,
			je.cheque_no,
			si.shipping_bill_number AS shipping_bill_no,
			c.igst_export_refund_receivable AS account

		FROM `tabJournal Entry` AS je

		LEFT JOIN `tabJournal Entry Account` AS jea
			ON jea.parent = je.name

		LEFT JOIN `tabSales Invoice` AS si
			ON si.name = je.cheque_no

		LEFT JOIN `tabCompany` AS c
			ON c.name = je.company

		WHERE
			je.voucher_type = 'Journal Entry'
			AND je.posting_date >= %(r_start_date)s
			AND je.posting_date <= %(r_end_date)s
			AND jea.debit_in_account_currency > 0
			AND si.igst_received != 1
			AND je.docstatus < 2
			AND je.company = %(company)s
			AND jea.account = c.igst_export_refund_receivable
	"""

	if list_of_je:
		query += " AND je.name NOT IN %(excluded_jv)s"
		values["excluded_jv"] = tuple(list_of_je)

	je_data = frappe.db.sql(
		query,
		values,
		as_dict=1
	)

	return je_data

def create_jv_on_submit(self,method):
	if(round(flt(self.total_debit_amount),4) == round(flt(self.script_amount),4)):
		igst_export_refund_receivable = frappe.db.get_value("Company", { "company_name": self.company}, "igst_export_refund_receivable")
		# meis_income_account = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_income_account")
		# meis_cost_center = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_cost_center")
		
		if not igst_export_refund_receivable:
			frappe.throw(_("Set IGST Export Refund Receivable Account in Company"))
		# elif not meis_income_account:
		# 	frappe.throw(_("Set Duty Drawback Income Account in Company"))
		# elif not meis_cost_center:
		# 	frappe.throw(_("Set Duty Drawback Cost Center in Company"))
		else:
			meis_jv = frappe.new_doc("Journal Entry")
			meis_jv.voucher_type = "Journal Entry"
			meis_jv.posting_date = self.posting_date
			meis_jv.company = self.company
			meis_jv.cheque_no = self.name
			meis_jv.cheque_date = self.posting_date
			meis_jv.user_remark = "IGST Refund against " + self.name 
			for row in self.igst_refund_details:
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

	
	

