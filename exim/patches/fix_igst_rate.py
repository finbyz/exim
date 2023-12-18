from __future__ import unicode_literals
import frappe

def execute():
	fix_igst_rate()

def fix_igst_rate():
	# Update the column using the appropriate syntax for the data type
	frappe.db.sql("""
		UPDATE `tabSales Invoice Item`
		SET igst_rate = 0
		WHERE CAST(igst_rate AS CHAR) = '' OR igst_rate IS NULL
	""")
	frappe.db.commit()