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
    total_drawback = 0
    total_rodtep = 0

    for d in self.items:
        if self.freight_calculated == "By Qty":
            d.freight = (d.qty * self.total_freight) / self.total_qty
        elif self.freight_calculated == "By Amount":
            d.freight = (d.base_amount * self.total_freight) / self.base_total
        elif self.freight_calculated == "Manual":
            total_freight += flt(d.freight)
        total_qty += flt(d.qty)
        total_packages += flt(d.no_of_packages)
        d.total_tare_weight = flt(d.tare_wt * d.no_of_packages)
        d.gross_wt = flt(d.total_tare_weight) + flt(d.qty)
        if self.fob_calculation:
            if self.shipping_terms in ["CIF", "CFR", "CNF", "CPT"]:
                d.fob_value = flt(d.base_amount) - flt(d.freight * self.conversion_rate) - flt(
                    d.insurance * self.conversion_rate
                )
            else:
                d.fob_value = flt(d.base_amount)
        total_tare_wt += flt(d.total_tare_weight)
        total_gr_wt += flt(d.gross_wt)
        total_insurance += flt(d.insurance)
        total_meis += flt(d.meis_value)
        total_drawback += d.duty_drawback_amount
        d.total_duty_drawback = total_drawback
        total_rodtep += d.meis_value

    self.total_qty = total_qty
    self.total_packages = total_packages
    self.total_gr_wt = total_gr_wt
    self.total_tare_wt = total_tare_wt
    if self.freight_calculated == "Manual":
        self.total_freight = total_freight
    self.insurance = total_insurance
    self.total_fob = self.total_fob_value / self.conversion_rate
    self.total_meis = total_meis
