# Copyright (c) 2023, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
# import datetime
from frappe import _
from frappe.utils import flt
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
	
	def on_submit(self):
		self.total_debit_amount=flt(self.total_debit_amount)-flt(self.round_off_amount)
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
	list_of_je = frappe.db.sql(f"""
		SELECT rcm.je_no , rd.journal_entry_ref
		From `tabDrawback Details` as rcm
		Join `tabDuty DrawBack Claim` as rd
		Where  rd.company='{company}' and rd.docstatus !=2
	""",as_list=True)
	je = []
	for row in list_of_je:
		for d in row:
			je.append(str(d))
	return je


@frappe.whitelist()
def journal_entry_list(start_date,end_date,company):
	list_of_je = exp_je_data(company)
	conditions = ""
	if list_of_je:
		conditions = " and je.name NOT IN {} ".format(
				"(" + ", ".join([f'"{l}"' for l in list_of_je]) + ")")
	r_start_date = start_date
	r_end_date = end_date 
	args = {
		'r_start_date':r_start_date,
		'r_end_date': r_end_date
	}
	
	je_data = frappe.db.sql(f""" 
		select je.name as je_no, jea.debit_in_account_currency as debit_amount , je.cheque_date, je.cheque_no, si.shipping_bill_number as shipping_bill_no, c.duty_drawback_receivable_account as account

		from `tabJournal Entry` as je
		LEFT JOIN `tabJournal Entry Account` as jea ON jea.parent = je.name
		Left JOIN `tabSales Invoice` as si ON si.name = je.cheque_no
		LEFT JOIN `tabCompany` as c ON c.name = je.company

		where je.voucher_type = "Duty Drawback Entry" 
		and je.posting_date >= %(r_start_date)s 
		and je.posting_date <= %(r_end_date)s
		and jea.debit_in_account_currency > 0
		and je.docstatus < 2 and je.company='{company}'
		{conditions}
	""",args,as_dict=1)
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
			if self.round_off_amount < 0.0:
				meis_jv.append("accounts", {
					"account": self.round_off_account,
					"credit_in_account_currency":-flt(self.round_off_amount),
				})
			elif self.round_off_amount > 0.0:
				meis_jv.append("accounts", {
					"account": self.round_off_account,
					"debit_in_account_currency":flt(self.round_off_amount),
				})
			
			try:
				meis_jv.save(ignore_permissions=True)
				meis_jv.submit()
				self.db_set('journal_entry_ref',meis_jv.name)
				if meis_jv.name:
					frappe.msgprint("Journal Entry Created Successfully {}".format(frappe.bold(meis_jv.name)))
			except Exception as e:
				frappe.throw(str(e))
				
