// Copyright (c) 2022, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt
let payment_entry_list = [];
cur_frm.fields_dict.invoice_no.get_query = function(doc) {
	return {
		query: "exim.query.get_invoce_no_based_on_customer"
	}
};

cur_frm.set_query("voucher_no", "brc_payment", function(doc) {
	return {
		query: "exim.query.get_invoce_no",
		filters: {
			'invoice_no': doc.invoice_no
		}
	}
});
frappe.ui.form.on('BRC Management', {
	onload: function (frm) {
        frm.trigger("add_unique_payment_entry");
	},

	before_save: function (frm) {
		frm.trigger("cal_total");
		frm.trigger("cal_bank_difference");
		frm.trigger("cal_bank_total_charges");
		frm.trigger("cal_total_brc_amount");
	},
	cal_total: function (frm) {
		let total_shipping_bill_amount = 0.0;
		if(frm.doc.shipping_bill_details){
			frm.doc.shipping_bill_details.forEach(function (d) {
				total_shipping_bill_amount += flt(d.shipping_bill_amount);
			})
		}
		frm.set_value("total_shipping_bill_amount", total_shipping_bill_amount);
	},
	cal_bank_difference: function(frm){
		if(frm.doc.brc_payment){
			frm.doc.brc_payment.forEach(function (d) {
				frappe.model.set_value(d.doctype, d.name, 'bank_charges', (flt(d.total_allocated_amount - d.brc_amount)));
			})
		}
	},
	cal_bank_total_charges: function(frm){
		let total_bank_charges = 0.0;
		if(frm.doc.brc_payment){
			frm.doc.brc_payment.forEach(function (d) {
				total_bank_charges += flt(d.bank_charges);
			})
		}
		frm.set_value("total_bank_charges", total_bank_charges);
	},
	cal_total_brc_amount: function(frm){
		let total_brc_amount = 0.0;
		let total_payment_receipt = 0.0;

		if(frm.doc.brc_payment){
			frm.doc.brc_payment.forEach(function (d) {
				total_brc_amount += flt(d.brc_amount);
				total_payment_receipt += flt(d.total_allocated_amount);
			})
		}
		frm.set_value("total_brc_amount", total_brc_amount);
		frm.set_value("total_payment_receipt", total_payment_receipt);
	},
	add_unique_payment_entry: function(frm){
		payment_entry_list = [];
		frm.doc.brc_payment.forEach(function(d){
			if(payment_entry_list.indexOf(d.voucher_no) === -1 && d.voucher_no ){
				payment_entry_list.push(d.voucher_no);
			}
		});
	}
});
frappe.ui.form.on('Shipping Bill Details', {
	shipping_bill_amount: function (frm, cdt, cdn) {
		frm.events.cal_total(frm);
	}
})
frappe.ui.form.on('BRC Payment', {
	brc_amount: function(frm, cdt, cdn){
		var d = locals[cdt][cdn];
		frm.events.cal_total_brc_amount(frm);
		frm.events.cal_bank_difference(frm);
	},
	bank_charges: function(frm,cdt,cdn){
		frm.events.cal_bank_total_charges(frm)
	},
	voucher_no: function(frm,cdt,cdn){
		let d = locals[cdt][cdn];

		frm.events.cal_total_brc_amount(frm);
		frm.events.add_unique_payment_entry(frm);
		
		if(payment_entry_list.includes(d.voucher_no)){
			frappe.throw("Payment Entry Number Must be Unique")
		}
	},
	brc_payment_remove: function (frm, cdt, cdn) {
		
		frm.events.cal_total_brc_amount(frm);
		frm.events.cal_bank_total_charges(frm);
		frm.events.add_unique_payment_entry(frm);
	}
})