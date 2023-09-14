import frappe
from frappe.utils import flt, cint, nowdate, cstr, now_datetime

def cal_total(self, method):
    total_qty = 0
    total_packages = 0
    total_gr_wt = 0
    total_tare_wt = 0
    total_freight = 0
    total_insurance = 0
    total_meis = 0

    for d in self.items:
        total_qty += flt(d.qty)
        total_packages += flt(d.no_of_packages)
        d.total_tare_weight = flt(d.tare_wt * d.no_of_packages)
        d.gross_wt = flt(d.total_tare_weight) + flt(d.qty)
        d.fob_value = flt(d.base_amount) - flt(d.freight * self.conversion_rate) - flt(d.insurance * self.conversion_rate)
        total_tare_wt += flt(d.total_tare_weight)
        total_gr_wt += flt(d.gross_wt)
        total_freight += flt(d.freight)
        total_insurance += flt(d.insurance)
        total_meis += flt(d.meis_value)
        
    self.total_qty = total_qty
    self.total_packages = total_packages
    self.total_gr_wt = total_gr_wt
    self.total_tare_wt = total_tare_wt
    self.freight = total_freight
    self.insurance = total_insurance
    self.total_fob = self.total_fob_value / self.conversion_rate
    self.total_meis = total_meis