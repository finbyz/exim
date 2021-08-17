# -*- coding: utf-8 -*-
# Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document

class ContractTerm(Document):
	def autoname(self):
		pass
		# if self.terms_based_on == "Letter of Credit":
		# 	if not self.lc_no:
		# 		frappe.throw(_("Mandatory Field LC No"))
		# 	self.name = self.lc_no

		# else:
		# 	if not self.document_no:
		# 		frappe.throw(_("Mandatory Field Document No"))
		# 	self.name = self.document_no

	def validate(self):
		if flt(self.contract_amount) < flt(self.total_net_amount):
			frappe.throw(_("Contract Amount should not be less than Total Net Amount"))

	def before_save(self):
		total_grand_amount = 0
		total_net_amount = 0

		for d in self.get('contract_term_order'):
			total_grand_amount += flt(d.grand_total)
			total_net_amount += flt(d.net_total)

		self.total_grand_amount = total_grand_amount
		self.total_net_amount = total_net_amount