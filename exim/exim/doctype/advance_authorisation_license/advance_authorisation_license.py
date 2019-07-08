# -*- coding: utf-8 -*-
# Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document

class AdvanceAuthorisationLicense(Document):
	def validate(self):
		# self.validate_references()
		self.calulate_total_imports_exports()
		self.validate_exports()
		self.validate_import_ratio()

	def validate_references(self):
		for row in self.get('imports'):
			if not row.purchase_invoice:
				frappe.throw(_("Purchase Invoice reference not found in Imports in row {}. Plase create Purchase Invoice for item {}.".format(row.idx, row.item_code)))

		for row in self.get('exports'):
			if not row.sales_invoice:
				frappe.throw(_("Sales Invoice reference not found in Exports in row {}. Plase create Sales Invoice for item {}.".format(row.idx, row.item_code)))

	def calulate_total_imports_exports(self):
		self.total_import_qty = sum([flt(d.quantity) for d in self.get('imports')])
		if self.total_import_amount < self.approved_amount:
			self.total_import_amount = sum([flt(d.cif_value) for d in self.get('imports')])
			self.remaining_license_amount = flt(self.approved_amount) - self.total_import_amount	
		else:
			frappe.throw(_("AdvanceAuthorisationLicense {} total approved amount is less than utilization".format(self.name)))
		self.total_export_qty = sum([flt(d.quantity) for d in self.get('exports')])
		self.total_export_amount = sum([flt(d.fob_value) for d in self.get('exports')])
		
		

	def validate_exports(self):
		remaining_exp_qty = flt(self.approved_qty) - flt(self.total_export_qty)
		# if remaining_exp_qty < 0:
		# 	frappe.msgprint(_("{0} quantity over exported for item {1}.".format(abs(remaining_exp_qty), self.export_item)))
	
		self.remaining_export_qty = remaining_exp_qty

		remaining_exp_amount = flt(self.total_license_amount) - flt(self.total_export_amount)
		# if remaining_exp_amount < 0:
		# 	frappe.msgprint(_("{0} amount over exported for item {1}.".format(abs(remaining_exp_amount), self.export_item)))

		self.remaining_export_amount = remaining_exp_amount

	def validate_import_ratio(self):
		for row in self.get('item_import_ratio'):
			if flt(row.ratio) > 1:
				frappe.throw(_("Ratio cannot be greater than 1"))

			row.approved_qty = flt(self.approved_qty * row.ratio, 2)

			import_qty = sum([flt(d.quantity) for d in self.get('imports') if d.item_code == row.item_code])
			if row.approved_qty - import_qty < 0:
				frappe.throw(_("Remaining import quantity is becoming negative for {} in {}".format(row.item_code,self.name)))
			else:
				row.total_import_qty = import_qty
				row.remaining_qty = flt(row.approved_qty) - import_qty
				import_amount = sum([flt(d.cif_value) for d in self.get('imports') if d.item_code == row.item_code])
			#if flt(row.approved_amount) - import_amount < 0:
			#	frappe.throw(_("Remaining import amount is becoming negative in {}".format(self.name)))
			#else:
				row.total_import_amount = import_amount
				row.remaining_amount = flt(row.approved_amount) - import_amount


@frappe.whitelist()
def license_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select distinct aal.name, ratio.total_import_qty, ratio.total_import_amount
			from `tabAdvance Authorisation License` aal
				LEFT JOIN `tabItem Import Ratio` ratio on (ratio.parent = aal.name)
			where ratio.item_code = %(item_code)s
		order by
			if(locate(%(_txt)s, aal.name), locate(%(_txt)s, aal.name), 99999)
		limit %(start)s, %(page_len)s """, {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
			'item_code': filters.get('item_code')
		})

@frappe.whitelist()
def get_license_details(aal, item_code):
	return frappe.db.sql("""select distinct aal.name, ratio.approved_qty, ratio.remaining_qty, 
				ratio.approved_amount, ratio.remaining_amount
			from `tabAdvance Authorisation License` aal
				LEFT JOIN `tabItem Import Ratio` ratio on (ratio.parent = aal.name)
			where aal.name = %(aal)s and ratio.item_code = %(item_code)s
		""", {'aal': aal, 'item_code': item_code}, as_dict = 1)[0]
