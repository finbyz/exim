import frappe
from frappe import flt

def cal_total(self):
    total_qty = 0
    total_packages = 0
    total_gr_wt = 0
    total_tare_wt = 0
    total_freight = 0
    total_insurance = 0

    for d in self.items:
        total_qty += flt(d.qty)
        total_packages += flt(d.no_of_packages)
        d.total_tare_weight = flt(d.tare_wt * d.no_of_packages)
        d.gross_wt = flt(d.total_tare_weight) + flt(d.qty)
        total_tare_wt += flt(d.total_tare_weight)
        total_gr_wt += flt(d.gross_wt)
        total_freight += flt(d.freight)
        total_insurance += flt(d.insurance)
        
    self.total_qty = total_qty
    self.total_packages = total_packages
    self.total_gr_wt = total_gr_wt
    self.total_tare_wt = total_tare_wt
