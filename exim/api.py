import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.contacts.doctype.address.address import get_company_address

@frappe.whitelist()
def si_validate(self, method):
	if self._action == 'submit':
		validate_document_checks(self)

@frappe.whitelist()
def si_on_submit(self, method):
	export_lic(self)
	create_jv(self)

@frappe.whitelist()
def si_on_cancel(self, method):
	export_lic_cancel(self)
	cancel_jv(self, method)
	
@frappe.whitelist()
def si_before_save(self,method):
	duty_calculation(self)
	#cal_total_fob_value(self)
	
@frappe.whitelist()
def pi_on_submit(self, method):
	import_lic(self)
	
@frappe.whitelist()
def pi_on_cancel(self, method):
	import_lic_cancel(self)

def create_jv(self):
	if self.currency != "INR":
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
					self.db_set('duty_drawback_jv',jv.name)
					
		if self.total_meis:
			meis_receivable_account = frappe.db.get_value("Company", { "company_name": self.company}, "meis_receivable_account")
			meis_income_account = frappe.db.get_value("Company", { "company_name": self.company}, "meis_income_account")
			meis_cost_center = frappe.db.get_value("Company", { "company_name": self.company}, "meis_cost_center")
			if not meis_receivable_account:
				frappe.throw(_("Set MEIS Receivable Account in Company"))
			elif not meis_income_account:
				frappe.throw(_("Set MEIS Income Account in Company"))
			elif not meis_cost_center:
				frappe.throw(_("Set MEIS Cost Center in Company"))
			else:
				meis_jv = frappe.new_doc("Journal Entry")
				meis_jv.voucher_type = "MEIS Entry"
				meis_jv.posting_date = self.posting_date
				meis_jv.company = self.company
				meis_jv.cheque_no = self.name
				meis_jv.cheque_date = self.posting_date
				meis_jv.user_remark = "MEIS against " + self.name + " for " + self.customer
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
		frappe.db.commit()
	
def cancel_jv(self, method):
	if self.duty_drawback_jv:
		jv = frappe.get_doc("Journal Entry", self.duty_drawback_jv)
		jv.cancel()
		self.duty_drawback_jv = ''
	if self.meis_jv:
		jv = frappe.get_doc("Journal Entry", self.meis_jv)
		jv.cancel()
		self.meis_jv = ''
	frappe.db.commit()
	

def duty_calculation(self):
	total_duty_drawback = 0.0;
	for row in self.items:
		if row.duty_drawback_rate and row.fob_value:
			duty_drawback_amount = flt(row.fob_value * row.duty_drawback_rate / 100.0)
			if row.maximum_cap == 1:
				if row.capped_amount < duty_drawback_amount:
					row.duty_drawback_amount = row.capped_amount
					row.effective_rate = flt(row.capped_amount / row.fob_value * 100.0)
				else:
					row.duty_drawback_amount = duty_drawback_amount
					row.effective_rate = row.duty_drawback_rate
			else:
				row.duty_drawback_amount = duty_drawback_amount
				
		row.fob_value = flt(row.base_amount)
		row.igst_taxable_value = flt(row.amount)
		total_duty_drawback += flt(row.duty_drawback_amount) or 0.0
		row.meis_value = flt(row.fob_value * row.meis_rate / 100.0)
		
	self.total_duty_drawback = total_duty_drawback
	
def cal_total_fob_value(self):
	total_fob = 0.0
	for row in self.items:
		if row.fob_value:
			total_fob += flt(row.fob_value)
	self.total_fob_value = flt(flt(total_fob) - (flt(self.freight) * flt(self.conversion_rate)) -(flt(self.insurance) * flt(self.conversion_rate)))
	
def export_lic(self):
	for row in self.items:
		if row.advance_authorisation_license:
			aal = frappe.get_doc("Advance Authorisation License", row.advance_authorisation_license)
			aal.append("exports", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"quantity": row.qty,
				"uom": row.uom,
				"fob_value" : flt(row.fob_value),
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
	else:
		frappe.db.commit()

def export_lic_cancel(self):
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
	else:
		frappe.db.commit()

def import_lic(self):
	for row in self.items:
		if row.advance_authorisation_license:
			aal = frappe.get_doc("Advance Authorisation License", row.advance_authorisation_license)
			aal.append("imports", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"quantity": row.qty,
				"uom": row.uom,
				"cif_value" : flt(row.cif_value),
				"currency" : self.currency,
				"shipping_bill_no": self.shipping_bill,
				"shipping_bill_date": self.shipping_bill_date,
				"port_of_loading" : self.port_of_loading,
				"port_of_discharge" : self.port_of_discharge,
				"purchase_invoice" : self.name,
			})

			aal.total_import_qty = sum([flt(d.quantity) for d in aal.imports])
			aal.total_import_amount = sum([flt(d.cif_value) for d in aal.imports])
			aal.save()
	else:
		frappe.db.commit()

def import_lic_cancel(self):
	doc_list = list(set([row.advance_authorisation_license for row in self.items if row.advance_authorisation_license]))

	for doc_name in doc_list:
		doc = frappe.get_doc("Advance Authorisation License", doc_name)
		to_remove = []

		for row in doc.imports:
			if row.parent == doc_name and row.purchase_invoice == self.name:
				to_remove.append(row)

		[doc.remove(row) for row in to_remove]
		doc.total_import_qty = sum([flt(d.quantity) for d in doc.imports])
		doc.total_import_amount = sum([flt(d.cif_value) for d in doc.imports])
		doc.save()
	else:
		frappe.db.commit()		
	
@frappe.whitelist()
def get_custom_address(party=None, party_type="Customer", ignore_permissions=False):

	if not party:
		return {}

	if not frappe.db.exists(party_type, party):
		frappe.throw(_("{0}: {1} does not exists").format(party_type, party))

	return _get_custom_address(party, party_type, ignore_permissions)

def _get_custom_address(party=None, party_type="Customer", ignore_permissions=False):

	out = frappe._dict({
		party_type.lower(): party
	})

	party = out[party_type.lower()]

	if not ignore_permissions and not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted for {0}").format(party), frappe.PermissionError)

	party = frappe.get_doc(party_type, party)
	
	set_custom_address_details(out, party, party_type)
	return out

def set_custom_address_details(out, party, party_type):
	billing_address_field = "customer_address" if party_type == "Lead" \
		else party_type.lower() + "_address"
	out[billing_address_field] = get_custom_default_address(party_type, party.name)
	
	# address display
	out.address_display = get_custom_address_display(out[billing_address_field])

def get_custom_address_display(address_dict):
	if not address_dict:
		return

	if not isinstance(address_dict, dict):
		address_dict = frappe.db.get_value("Address", address_dict, "*", as_dict=True, cache=True) or {}

	name, template = get_custom_address_templates(address_dict)

	try:
		return frappe.render_template(template, address_dict)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template {0}").format(name))

def get_custom_address_templates(address):
	result = frappe.db.get_value("Address Template", \
		{"country": address.get("country")}, ["name", "template"])

	if not result:
		result = frappe.db.get_value("Address Template", \
			{"is_default": 1}, ["name", "template"])

	if not result:
		frappe.throw(_("No default Address Template found. Please create a new one from Setup > Printing and Branding > Address Template."))
	else:
		return result

def get_custom_default_address(doctype, name, sort_key='is_primary_address'):
	'''Returns default Address name for the given doctype, name'''
	out = frappe.db.sql('''select
			parent, (select name from tabAddress a where a.name=dl.parent) as name,
			(select address_type from tabAddress a where a.name=dl.parent and a.address_type="Consignee-Custom") as address_type
			from
			`tabDynamic Link` dl
			where
			link_doctype=%s and
			link_name=%s and
			parenttype = "Address" and
			(select address_type from tabAddress a where a.name=dl.parent)="Consignee-Custom"
		'''.format(sort_key),(doctype, name))

	if out:
		return sorted(out, key = functools.cmp_to_key(lambda x,y: cmp(y[1], x[1])))[0][0]
	else:
		return None

@frappe.whitelist()
def company_address(company):
	return get_company_address(company)

@frappe.whitelist()
def make_lc(source_name, target_doc=None):
	def postprocess(source, target):
		target.append('contract_term_order', {
				'sales_order': source.name,
				'grand_total': source.grand_total,
				'net_total': source.net_total,
			})

	doclist = get_mapped_doc("Sales Order", source_name, {
			"Sales Order": {
				"doctype": "Contract Term",
				"field_map": {
					"name": "sales_order",
					"transaction_date":"contract_date",
					"grand_total": "contract_amount",
				},	
			},		
		}, target_doc, postprocess)

	return doclist
	
def contract_and_lc_filter(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	so_list = filters.get("sales_order_item")

	return frappe.db.sql("""
		SELECT DISTINCT ct.name
		FROM `tabContract Term` AS ct JOIN `tabContract Term Order` as cto ON (cto.parent = ct.name) 
		WHERE cto.sales_order in (%s) """% ', '.join(['%s']*len(so_list)), tuple(so_list))

		
def validate_document_checks(self):
	if not all([row.checked for row in self.get('sales_invoice_export_document_item')]):
		frappe.throw(_("Not all documents are checked for Export Documents"))

	elif not all([row.checked for row in self.get('sales_invoice_contract_term_check')]):
		frappe.throw(_("Not all documents are checked for Document Checks"))
		
@frappe.whitelist()
def docs_before_naming(self, method):
	from erpnext.accounts.utils import get_fiscal_year

	date = self.get("transaction_date") or self.get("posting_date") or getdate()

	fy = get_fiscal_year(date)[0]
	fiscal = frappe.db.get_value("Fiscal Year", fy, 'fiscal')

	if fiscal:
		self.fiscal = fiscal
	else:
		fy_years = fy.split("-")
		fiscal = fy_years[0][2:] + fy_years[1][2:]
		self.fiscal = fiscal
		