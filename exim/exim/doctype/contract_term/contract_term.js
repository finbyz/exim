cur_frm.add_fetch("sales_order", "currency", "currency");
cur_frm.add_fetch("sales_order", "port_of_loading", "port_of_loading");
cur_frm.add_fetch("sales_order", "port_of_discharge", "port_of_discharge");
cur_frm.add_fetch("sales_order", "grand_total", "contract_amount");
cur_frm.add_fetch("sales_order", "transaction_date", "contract_date");

this.frm.add_fetch("sales_order", "grand_total", "grand_total");
this.frm.add_fetch("sales_order", "net_total", "net_total");

cur_frm.fields_dict.lc_opening_bank.get_query = function(doc) {
	return {
		filters: {
			'bank_type': 'Foreign Bank'
		}
	}
};

cur_frm.fields_dict.contract_term_order.grid.get_field("sales_order").get_query = function(doc,cdt,cdn) {
	let d = locals[cdt][cdn];
	return {
		filters: {
			"currency": doc.currency,
			"docstatus": 1
		}
	}
};

frappe.ui.form.on('Contract Term', {
	// validate: function(frm){
	// 	if(frm.doc.contract_amount <= frm.doc.total_net_amount){
	// 		frappe.msgprint(__("Contract Amount should not be less than Total Net Amount"));
	// 		frappe.validated = false
	// 	}
	// },
	before_save: function(frm){
		/*frm.trigger("cal_contract_orders")*/
		if(frm.doc.terms_based_on == "CAD"){
			frm.set_value('document_no', frm.doc.sales_order);
		}
	},
	cal_contract_orders: function(frm){
		let total_grand_amount = 0.0;
		let total_net_amount = 0.0;
		frm.doc.contract_term_order.forEach(function(d){
			total_grand_amount += flt(d.grand_total);
			total_net_amount += flt(d.net_total);
		});
		frm.set_value('total_grand_amount', total_grand_amount);
		frm.set_value('total_net_amount', total_net_amount);
	},
	sales_order: function(frm){
		frm.set_currency_labels(["contract_amount"], frm.doc.currency);
	},
	percentage_credit_amount_tolerance:function(frm){
		frm.trigger("cal_contract_amount");
	},
	contract_amount:function(frm){
		frm.trigger("cal_contract_amount");
	},
	contract_side:function(frm){
		frm.trigger("cal_contract_amount");
	},
	cal_contract_amount: function(frm){
		let perToAmount = flt(frm.doc.contract_amount * frm.doc.percentage_credit_amount_tolerance)/100;
		let lowerBound = flt(frm.doc.contract_amount - perToAmount);
		let upperBound = flt(frm.doc.contract_amount + perToAmount);

		if (frm.doc.contract_side=="&lt;"){
			frm.set_value('amount_allowed_to',frm.doc.contract_amount);
			frm.set_value('amount_allowed_from',lowerBound);
		}
		else if (frm.doc.contract_side=="&gt;"){			
			frm.set_value('amount_allowed_to',upperBound);
			frm.set_value('amount_allowed_from',frm.doc.contract_amount);
		}
		else {
			frm.set_value('amount_allowed_to',upperBound);
			frm.set_value('amount_allowed_from',lowerBound);
		}
	},
});


frappe.ui.form.on('Contract Term Order', {
	contract_term_order_remove: function(frm, cdt, cdn){
		frm.events.cal_contract_orders(frm);
	},
	sales_order: function(frm, cdt, cdn){
		frm.events.cal_contract_orders(frm);
	},
});
