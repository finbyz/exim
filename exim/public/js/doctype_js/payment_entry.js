
this.frm.add_fetch('forward_contract', 'booking_rate', 'forward_rate');
this.frm.add_fetch('forward_contract', 'amount', 'amount');
this.frm.add_fetch('forward_contract', 'maturity_from', 'maturity_from');
this.frm.add_fetch('forward_contract', 'maturity_to', 'maturity_to');
this.frm.add_fetch('forward_contract', 'amount_outstanding', 'amount_outstanding');
this.frm.add_fetch('forward_contract', 'amount_outstanding', 'amount_utilized');

this.frm.cscript.onload = function(frm) {
	if (this.frm.doc.paid_to_account_currency == 'INR'){
		this.frm.set_query("forward_contract","forwards", function() {
			return {
				"filters": {
					"hedge": "Export",
					"status": "Open",
					"docstatus": 1,
					"amount_outstanding": ['>', '0'],
					"currency": cur_frm.doc.paid_from_account_currency
				}
			};
		});
	}
	else {
		this.frm.set_query("forward_contract","forwards", function() {
			return {
				"filters": {
					"hedge": "Import",
					"status": "Open",
					"docstatus": 1,
					"amount_outstanding": ['>', '0'],
					"currency": cur_frm.doc.paid_to_account_currency
				}
			};
		});
	}
}

frappe.ui.form.on("Payment Entry", {
    paid_to: function(frm){
        cur_frm.refresh();
    // if (frm.doc.paid_to_account_currency == 'INR'){
	// 	frm.set_query("forward_contract","forwards", function() {
	// 		return {
	// 			"filters": {
	// 				"hedge": "Export",
	// 				"status": "Open",
	// 				"docstatus": 1,
	// 				"amount_outstanding": ['>', '0'],
	// 				"currency": cur_frm.doc.paid_from_account_currency
	// 			}
	// 		};
	// 	});
	// }
	// else {
	// 	frm.set_query("forward_contract","forwards", function() {
	// 		return {
	// 			"filters": {
	// 				"hedge": "Import",
	// 				"status": "Open",
	// 				"docstatus": 1,
	// 				"amount_outstanding": ['>', '0'],
	// 				"currency": cur_frm.doc.paid_to_account_currency
	// 			}
	// 		};
	// 	});
	// }
        
    },
	onload: function(frm){
		if(frm.doc.__islocal && frm.doc.payment_type== "Pay"){
			frm.set_value('print_heading', "Payment Advice");
		}
		var df = frappe.meta.get_docfield("Forward Utilization","forward_amount", cur_frm.doc.name);
		df.options="paid_from_account_currency";
		
		df = frappe.meta.get_docfield("Forward Utilization","amount_outstanding", cur_frm.doc.name);
		df.options="paid_from_account_currency";

		df = frappe.meta.get_docfield("Forward Utilization","amount_utilized", cur_frm.doc.name);
		df.options="paid_from_account_currency";
	},
	
	validate: function(frm){
		if(cstr(frm.doc.forwards)){
			if(frm.doc.total_amount_utilized != frm.doc.paid_amount) {
				frappe.throw(__("Total Amount Utilized must be same as Paid Amount."))
			}
		}
	},

	payment_type: function(frm){
		if(frm.payment_type == "Pay"){
			frm.set_value('print_heading', "Payment Advice");
		}
		if(frm.payment_type == "Receive"){
			frm.set_value('print_heading', "Payment Receipt");
		}
	},
// 	party: function(frm) {
// 		frappe.call({
// 			method:"elkins.api.get_party_details",
// 			args:{
// 				party: frm.doc.party,
// 				party_type: frm.doc.party_type
// 			},
// 			callback: function(r){
// 				if(r.message){
// 					frm.set_value('contact_person', r.message.contact_person)
// 					frm.set_value('email_id', r.message.contact_email)
// 					frm.set_value ('party_name', frm.doc.party)
// 				}
// 			}
// 		});
// 	},
	contact_person: function(frm) {
		erpnext.utils.get_contact_details(frm);
	},
	average_forward_rate: function(frm) {
		if(frm.doc.average_forward_rate){
			frm.set_value('source_exchange_rate', frm.doc.average_forward_rate);
		}
		else {
			var company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;
			frm.events.set_current_exchange_rate(frm, "source_exchange_rate", frm.doc.paid_from_account_currency, company_currency);
		}
	},
	cal_average_forward_rate: function(frm){
		let total_forward_rate = 0;
		$.each(frm.doc.forwards, function(index, row){
			total_forward_rate += flt(row.forward_rate);
		});
		frm.set_value("average_forward_rate", flt(total_forward_rate / (frm.doc.forwards.length || 1)));
	},
	cal_total_amount_utilized: function(frm){
		let total_amount_utilized = 0;
		$.each(frm.doc.forwards, function(index, row){
			total_amount_utilized += flt(row.amount_utilized);
		});
		frm.set_value("total_amount_utilized", total_amount_utilized);
	},
});

frappe.ui.form.on("Forward Utilization", {
	forwards_remove:function(frm,cdt,cdn){
		frm.events.cal_average_forward_rate(frm);
		frm.events.cal_total_amount_utilized(frm);
	},
	forward_rate:function(frm,cdt,cdn){
		frm.events.cal_average_forward_rate(frm);
	},
	amount_utilized:function(frm,cdt,cdn){
		frm.events.cal_total_amount_utilized(frm);
	},
});
