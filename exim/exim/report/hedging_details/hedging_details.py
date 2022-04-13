from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate
import datetime


def execute(filters=None):
	return HedgingDetailsReport(filters).run()

class HedgingDetailsReport(object):
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.columns = []
		self.data = []
		self.dist_months = []

	def run(self):
		self.get_columns()
		self.get_data()
		self.get_dist_months()
		self.get_forward_details()
		self.get_chart_data()

		return self.columns, self.data, None, self.chart

	def get_data(self):
		currency = self.filters.get('currency') or "INR"
		if self.filters.get('currency'):
			conditions = "= %s"
		else:
			conditions = "!= %s"

		self.currency_cond = conditions % currency
		
		self.data = frappe.db.sql("""
			SELECT name as sales_order, transaction_date, customer, currency, 
				(grand_total - (advance_paid / conversion_rate)) as total_amount, conversion_rate as rate, 
				base_grand_total as inr_amount, delivery_date, status 
			from `tabSales Order`
			where docstatus = 1 and status not in ('Closed', 'Completed')
				and amount_hedged < grand_total and currency {conditions}
			order by delivery_date """.format(conditions=conditions), currency, as_dict=1)

		self.forward_data = frappe.get_list("Forward Booking",
			filters = {'docstatus': 1, 'currency': self.currency_cond.split() },
			fields = ['name', 'maturity_to', 'booking_date', 'booking_rate', 'amount_outstanding'],
			order_by = "maturity_to")

	def get_dist_months(self):
		for row in self.data:
			delivery_date = getdate(row.delivery_date)
			if str(delivery_date.strftime("%b-%Y")) not in self.dist_months:
				self.dist_months.append(str(delivery_date.strftime("%b-%Y")))

		for row in self.forward_data:
			delivery_date = getdate(row.maturity_to)
			if str(delivery_date.strftime("%b-%Y")) not in self.dist_months:
				self.dist_months.append(str(delivery_date.strftime("%b-%Y")))
		
		sorted(self.dist_months, key=lambda x: datetime.datetime.strptime(x, '%b-%Y'))

	def get_forward_details(self):
		current_idx = 0

		for month in self.dist_months:
			row_data = [d for d in self.data if d.get('delivery_date') and str(getdate(d.delivery_date).strftime("%b-%Y")) == month]
			fwd_data = [d for d in self.forward_data if str(getdate(d.maturity_to).strftime("%b-%Y")) == month]

			row_data_len = len(row_data)
			fwd_data_len = len(fwd_data)

			if row_data_len:
				if row_data_len > fwd_data_len:
					idx = current_idx
					for d in fwd_data:
						self.data[idx].update({
								'forward_booking': d.name,
								'booking_date': d.booking_date,
								'booking_rate': d.booking_rate,
								'booking_amount': d.amount_outstanding,
								'maturity_to': d.maturity_to
							})

						idx += 1

				else:
					idx = current_idx
					diff = fwd_data_len - row_data_len

					for d in fwd_data[:row_data_len]:
						self.data[idx].update({
								'forward_booking': d.name,
								'booking_date': d.booking_date,
								'booking_rate': d.booking_rate,
								'booking_amount': d.amount_outstanding,
								'maturity_to': d.maturity_to
							})
						idx += 1

					for d in fwd_data[row_data_len:]:
						self.data.insert(idx, {
								'forward_booking': d.name,
								'booking_date': d.booking_date,
								'booking_rate': d.booking_rate,
								'booking_amount': d.amount_outstanding,
								'maturity_to': d.maturity_to
							})
						idx += 1
					current_idx += diff

				current_idx += row_data_len

			else:
				idx = current_idx
				for d in fwd_data:
					self.data.insert(idx, {
							'forward_booking': d.name,
							'booking_date': d.booking_date,
							'booking_rate': d.booking_rate,
							'booking_amount': d.amount_outstanding,
							'maturity_to': d.maturity_to,
							'currency': self.filters.get('currency') or "INR",
						})

					idx += 1

				current_idx += fwd_data_len

	def get_chart_data(self):
		amount_data, hedged_data, unhedged_data, labels= [], [], [], []
		
		for month in self.dist_months:
			amount = hedged = unhedged = 0
			for row in self.data:
				if row.get('delivery_date'):
					if str(getdate(row.get('delivery_date')).strftime("%b-%Y")) == month:
						amount += row.total_amount
						hedged += row.get('booking_amount', 0.0)
						unhedged += flt(row.total_amount) - row.get('booking_amount', 0.0)
				elif row.get('maturity_to'):
					if str(getdate(row.get('maturity_to')).strftime("%b-%Y")) == month:
						hedged += row.get('booking_amount', 0.0)
						unhedged += 0 - row.get('booking_amount', 0.0)
					
			amount_data.append(round(amount, 2))
			hedged_data.append(round(hedged, 2))
			unhedged_data.append(round(unhedged, 2))
			labels.append(month)

		self.data.append({
			'sales_order': "Total",
			'total_amount': sum(amount_data),
			'rate': sum([flt(d.get('total_amount')) * flt(d.get('rate')) for d in self.data]) / (sum(amount_data) or 1) if amount_data else 0,
			'amount_unhedged': sum(unhedged_data),
			'booking_rate': sum([flt(d.get('booking_rate')) * flt(d.get('booking_amount')) for d in self.data]) / (sum(hedged_data) or 1) if hedged_data else 0,
			'booking_amount': sum(hedged_data),
			'inr_amount': sum([flt(d.get('inr_amount')) for d in self.data]),
			'currency': self.filters.get('currency') or 'INR'
		})
			
		labels.append("Total")
		amount_data.append(round(sum(amount_data), 2))
		hedged_data.append(round(sum(hedged_data), 2))
		unhedged_data.append(round(sum(unhedged_data), 2))
		datasets = []
		
		if amount_data:
			datasets.append({
				'name': "Total Amount",
				'values': amount_data
			})
		
		if hedged_data:
			datasets.append({
				'name': "Total Forwards",
				'values': hedged_data
			})
		
		if unhedged_data:
			datasets.append({
				'name': "Total Unhedged",
				'values': unhedged_data
			})
		
		self.chart = {
			"data": {
				'labels': labels,
				'datasets': datasets
			},
			"type": "bar"
		}

	def get_columns(self):
		self.columns = [
			{
				"fieldname": "sales_order",
				"label": _("Sales Order"),
				"fieldtype": "Link",
				"options": "Sales Order",
				"width": 100
			},
			{
				"fieldname": "transaction_date",
				"label": _("Transaction Date"),
				"fieldtype": "Date",
				"width": 100
			},
			{
				"fieldname": "customer",
				"label": _("Customer"),
				"fieldtype": "Link",
				"options": "Customer",
				"width": 180
			},
			{
				"fieldname": "currency",
				"label": _("Currency"),
				"fieldtype": "Link",
				"options": "Currency",
				"width": 70
			},
			{
				"fieldname": "total_amount",
				"label": _("Total Amount"),
				"fieldtype": "Currency",
				"options": "currency",
				"width": 100
			},
			{
				"fieldname": "rate",
				"label": _("Rate"),
				"fieldtype": "Float",
				"width": 80
			},
			{
				"fieldname": "inr_amount",
				"label": _("INR Amount"),
				"fieldtype": "Currency",
				"width": 100
			},
			{
				"fieldname": "delivery_date",
				"label": _("Delivery Date"),
				"fieldtype": "Date",
				"width": 100
			},
			{
				"fieldname": "forward_booking",
				"label": _("Forward Booking"),
				"fieldtype": "Link",
				"options": "Forward Booking",
				"width": 110
			},
			{
				"fieldname": "booking_date",
				"label": _("Booking Date"),
				"fieldtype": "Date",
				"width": 100
			},
			{
				"fieldname": "booking_rate",
				"label": _("Forward Rate"),
				"fieldtype": "Currency",
				"options": "currency",
				"width": 100
			},
			{
				"fieldname": "booking_amount",
				"label": _("Outstanding Amount"),
				"fieldtype": "Currency",
				"options": "currency",
				"width": 100
			},
			{
				"fieldname": "status",
				"label": _("Status"),
				"fieldtype": "Data",
				"width": 150
			},
		]