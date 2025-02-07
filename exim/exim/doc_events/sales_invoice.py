import frappe
from frappe import _
from frappe.utils import flt


def before_save(self, method):
	calculate_total(self)
	duty_calculation(self)
	meis_calculation(self)


def validate(self, method):
	if self._action == 'submit':
		validate_document_checks(self)


def on_submit(self, method):
	export_lic(self)
	create_jv(self)
	create_brc(self)
	create_jv_with_gst(self)


def on_cancel(self, method):
	cancel_export_lic(self)
	cancel_jv(self)


def calculate_total(self):
	total_qty = 0
	total_packages = 0
	total_gr_wt = 0
	total_tare_wt = 0
	total_freight = 0
	total_insurance = 0
	total_meis = 0
	total_drawback = 0
	total_rodtep = 0
	total_fob_value = 0
	total_pallets = 0

	if self.gst_category == "Overseas" and not self.manually_enter_fob_value and self.freight_calculated in ["By Qty", "By Amount"] and self.shipping_terms not in ["CIF", "CFR", "CNF", "CPT"]:
		frappe.msgprint(f"To calculate item wise freight please ensure shipping terms are set either of {frappe.bold('CIF, CFR, CNF OR CPT')}.")

	for row in self.items:
		if self.freight_calculated == "By Qty":
			row.freight = (row.qty * self.freight) / self.total_qty
			row.insurance = (row.qty * self.insurance) / self.total_qty
		elif self.freight_calculated == "By Amount":
			row.freight = (row.base_amount * self.freight) / self.base_total
			row.insurance = (row.base_amount * self.insurance) / self.base_total
		else:
			total_freight += flt(row.freight)
			total_insurance += flt(row.insurance)
		
		total_qty += flt(row.qty)
		total_packages += flt(row.no_of_packages)

		row.total_tare_weight = flt(row.tare_wt * row.no_of_packages)
		
		pallet = flt(row.pallet_weight) * flt(row.total_pallets)
		row.gross_wt = flt(row.total_tare_weight) + (flt(row.qty) * (flt(row.weight_per_unit) or 1)) + flt(pallet)
		
		if not self.manually_enter_fob_value and self.gst_category == "Overseas":
			if self.shipping_terms in ["CIF", "CFR", "CNF", "CPT"]:
				row.fob_value = flt(row.base_amount) - flt(row.freight * self.conversion_rate) - flt(row.insurance * self.conversion_rate)
			else:
				row.fob_value = flt(row.base_amount)
		
		total_tare_wt += flt(row.total_tare_weight)
		total_gr_wt += flt(row.gross_wt)
		total_insurance += flt(row.insurance)
		total_meis += flt(row.meis_value)
		total_drawback += row.duty_drawback_amount
		row.total_duty_drawback = total_drawback
		total_rodtep += row.meis_value
		total_fob_value += flt(row.fob_value)
		total_pallets += flt(row.total_pallets)
	
	self.total_qty = total_qty
	self.total_packages = total_packages
	self.total_gr_wt = total_gr_wt
	self.total_tare_wt = total_tare_wt
	if self.freight_calculated == "Manual":
		self.freight = total_freight
		self.insurance = total_insurance
	self.total_meis = total_meis
	self.total_fob_value = total_fob_value
	self.total_pallets = total_pallets


def duty_calculation(self):
	parent_meta = frappe.get_meta(self.doctype)

	if parent_meta.has_field('total_duty_drawback') and frappe.db.get_value('Address', self.customer_address, 'country') != "India":
		total_duty_drawback = 0.0
		for row in self.items:
			child_meta = frappe.get_meta(row.doctype)
			if child_meta.has_field('duty_drawback_rate') and row.duty_drawback_rate and row.fob_value:
				duty_drawback_amount = flt(row.fob_value * row.duty_drawback_rate / 100.0)
				if child_meta.has_field('duty_drawback_amount'):
					if row.maximum_cap == 1:
						if row.capped_amount < duty_drawback_amount:
							row.duty_drawback_amount = row.capped_amount
							row.effective_rate = flt(row.capped_amount / row.fob_value * 100.0)
						else:
							row.duty_drawback_amount = duty_drawback_amount
							row.effective_rate = row.duty_drawback_rate
					else:
						row.duty_drawback_amount = duty_drawback_amount

			row.igst_taxable_value = flt(row.amount)
			if child_meta.has_field('duty_drawback_amount'):
				total_duty_drawback += flt(row.duty_drawback_amount) or 0.0

		self.total_duty_drawback = total_duty_drawback


def meis_calculation(self):
	if frappe.db.get_value('Address', self.customer_address, 'country') != "India":
		total_meis = 0.0
		for row in self.items:
			if row.fob_value and row.meis_rate:
				meis_value = flt(row.fob_value * row.meis_rate / 100.0)
				row.meis_value = meis_value

				total_meis += flt(row.meis_value)
		
		self.total_meis = total_meis


def validate_document_checks(self):
	if self.get('sales_invoice_export_document_item') and not all([row.checked for row in self.get('sales_invoice_export_document_item')]):
		frappe.throw(_("Not all documents are checked for Export Documents"))

	elif self.get('sales_invoice_contract_term_check') and not all([row.checked for row in self.get('sales_invoice_contract_term_check')]):
		frappe.throw(_("Not all documents are checked for Document Checks"))


def export_lic(self):
	for row in self.items:
		if row.get('advance_authorisation_license'):
			aal = frappe.get_doc("Advance Authorisation License", row.advance_authorisation_license)
			aal.append("exports", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"quantity": row.qty,
				"uom": row.uom,
				"fob_value" : flt(row.fob_value) / self.conversion_rate,
				"currency" : self.currency,	
				"shipping_bill_no": self.shipping_bill_number,
				"shipping_bill_date": self.shipping_bill_date,
				"port_of_loading" : self.port_of_loading,
				"port_of_discharge" : self.port_of_discharge,
				"sales_invoice" : self.name,
			})

			aal.total_export_qty = sum([flt(d.quantity) for d in aal.exports])
			aal.total_export_amount = sum([flt(d.fob_value) for d in aal.exports])
			aal.save()

def create_jv_with_gst(self):
    if not (self.get("is_export_with_gst") and self.get("taxes")):
        return

    taxes = self.get("taxes")[0]
    company_gst_payable_account = frappe.db.get_value(
        "Company", {"company_name": self.company}, "igst_export_refund_receivable"
    )
    currency_precision = frappe.get_precision("Journal Entry Account", "debit_in_account_currency")
    jv = frappe.get_doc(
        {
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": self.posting_date,
            "cheque_date": self.posting_date,
            "multi_currency": 1,
            "company": self.company,
            "company_gstin": self.company_gstin,
            "branch": self.branch,
            "cheque_no": self.name,
            "accounts": [
                {
                    "account": self.debit_to,
                    "exchange_rate": flt(self.conversion_rate),
                    "credit_in_account_currency": flt(taxes.tax_amount,currency_precision),
                    "debit_in_account_currency": 0,
                    "party_type": "Customer",
                    "party": self.customer,
                    "cost_center":self.cost_center,
                    "reference_type": self.doctype,
                    "reference_name": self.name,
                },
                {
                    "account": company_gst_payable_account,
                    "credit_in_account_currency": 0,
                    "debit_in_account_currency": flt(taxes.tax_amount,currency_precision) * self.conversion_rate,
                    "exchange_rate": 1,
                    "cost_center":self.cost_center
                },
            ],
        }
    )
    
    jv.save(ignore_permissions=True)
    jv.submit()
    meta = frappe.get_meta(self.doctype)
    if meta.has_field("igst_refund_jv"):
        self.db_set("igst_refund_jv", jv.name)
        


def create_jv(self):
	if frappe.db.get_value('Address', self.customer_address, 'country') != "India":
		meta = frappe.get_meta(self.doctype)
		if meta.has_field('total_duty_drawback'):
			if self.total_duty_drawback:
				drawback_receivable_account = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_receivable_account")
				drawback_income_account = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_income_account")
				drawback_cost_center = frappe.db.get_value("Company", { "company_name": self.company}, "duty_drawback_cost_center")
				if not drawback_receivable_account:
					frappe.throw(_("Set Duty Drawback Receivable Account in Company"))
				elif not drawback_income_account:
					frappe.throw(_("Set Duty Drawback Income Account in Company"))
				elif not drawback_cost_center:
					frappe.throw(_("Set Duty Drawback Cost Center in Company"))
				else:
					jv = frappe.new_doc("Journal Entry")
					jv.voucher_type = "Duty Drawback Entry"
					jv.posting_date = self.posting_date
					jv.company = self.company
					jv.cheque_no = self.name
					jv.cheque_date = self.posting_date
					jv.user_remark = "Duty draw back against " + self.name + " for " + self.customer
					jv.append("accounts", {
						"account": drawback_receivable_account,
						"cost_center": drawback_cost_center,
						"debit_in_account_currency": self.total_duty_drawback
					})
					jv.append("accounts", {
						"account": drawback_income_account,
						"cost_center": drawback_cost_center,
						"credit_in_account_currency": self.total_duty_drawback
					})
					try:
						jv.save(ignore_permissions=True)
						jv.submit()
					except Exception as e:
						frappe.throw(str(e))
					else:
						meta = frappe.get_meta(self.doctype)
						if meta.has_field('duty_drawback_jv'):
							self.db_set('duty_drawback_jv',jv.name)

		if self.get('total_meis'):
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
				meis_jv.user_remark = "RODTEP against " + self.name + " for " + self.customer
				meis_jv.append("accounts", {
					"account": meis_receivable_account,
					"cost_center": meis_cost_center,
					"debit_in_account_currency": self.total_meis
				})
				meis_jv.append("accounts", {
					"account": meis_income_account,
					"cost_center": meis_cost_center,
					"credit_in_account_currency": self.total_meis
				})
				
				try:
					meis_jv.save(ignore_permissions=True)
					meis_jv.submit()
				except Exception as e:
					frappe.throw(str(e))
				else:
					self.db_set('meis_jv',meis_jv.name)


def create_brc(self):
	if frappe.db.get_value('Address', self.customer_address, 'country') != "India" and frappe.db.exists("DocType", "BRC Management"):
		brc = frappe.new_doc("BRC Management")
		brc.invoice_no = self.name
		if not self.is_return and self.shipping_bill_number and self.shipping_bill_date and self.rounded_total:
			brc.append("shipping_bill_details", {
				"shipping_bill": self.shipping_bill_number,
				"shipping_date": self.shipping_bill_date,
				"shipping_bill_amount": self.rounded_total
			})
		brc.save(ignore_permissions=True)


def cancel_export_lic(self):
	doc_list = list(set([row.advance_authorisation_license for row in self.items if row.advance_authorisation_license]))

	for doc_name in doc_list:
		doc = frappe.get_doc("Advance Authorisation License", doc_name)
		to_remove = []

		for row in doc.exports:
			if row.parent == doc_name and row.sales_invoice == self.name:
				to_remove.append(row)

		[doc.remove(row) for row in to_remove]
		doc.total_export_qty = sum([flt(d.quantity) for d in doc.exports])
		doc.total_export_amount = sum([flt(d.fob_value) for d in doc.exports])
		doc.save()


def cancel_jv(self):
	meta = frappe.get_meta(self.doctype)
	if meta.has_field('duty_drawback_jv'):
		if self.duty_drawback_jv:
			jv = frappe.get_doc("Journal Entry", self.duty_drawback_jv)
			jv.cancel()
			self.db_set('duty_drawback_jv','')
	if meta.has_field('meis_jv'):
		if self.get('meis_jv'):
			jv = frappe.get_doc("Journal Entry", self.meis_jv)
			jv.cancel()
			self.db_set('meis_jv','')
