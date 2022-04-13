// Copyright (c) 2022, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt


let set_currency = 0;

cur_frm.fields_dict.bank.get_query = function(doc) {
	return {
		filters: {
			"bank_type": "Indian Bank",
		}
	}
};

cur_frm.fields_dict.bank_account.get_query = function(doc){
	return {
		filters: {
			'is_group': 0,
			'account_currency': "INR",
			'account_type': "Bank"
		}
	}
}

cur_frm.fields_dict.cancellation_details.grid.get_field('bank_account').get_query = function(doc){
	return {
		filters: {
			'is_group': 0,
			'account_currency': "INR",
			'account_type': "Bank"
		}
	}
}

//Filter Purchase & Sales Order
cur_frm.set_query("document", "forward_booking_underlying", function(doc, cdt, cdn){
	var d = locals[cdt][cdn];
	return {
		filters: [
			[d.link_to, "docstatus", "=", "1"],
			[d.link_to, "currency", "=", doc.currency],
			[d.link_to, "status", "!=", "Completed"],
			[d.link_to, "status", "!=", "Closed"],
			//[d.link_to, "amount_unhedged", ">", 0]
		]
	};
});


frappe.ui.form.on("Forward Booking", {
	onload: function(frm){
		if(frm.doc.__islocal) {
			frm.set_value("currency", "USD");
		}
	},
	validate:function(frm){
		if (frm.doc.total_underlying>frm.doc.amount){
			frappe.throw("Amount underlying should not be greater than forward booking amount.")
		}
	},
	hedge: function(frm){
		var df = frappe.meta.get_docfield("Forward Booking Underlying","link_to", frm.doc.name);
		if(frm.doc.hedge == "Export"){
			df.options = ["Sales Order", "Sales Invoice"]
		}
		else if(frm.doc.hedge == "Import"){
			df.options = ["Purchase Order", "Purchase Invoice"]
		}
		frm.refresh_field("forward_booking_underlying");
	},
	currency: function(frm){
		if(frm.doc.currency == 'INR' && !set_currency){
			frm.set_value("currency", "USD");
			set_currency = 1;
		}
	},
	// before_save: function(frm){
	// 	frm.trigger("forward_booking_calculation");
	// 	frm.trigger("cal_calcellation_details");
	// 	frm.trigger("calculate_outstanding");
	// 	frm.trigger("calculate_rate_diff");
	// },
	
	date_validation: function(frm){
		if (frm.doc.maturity_from > frm.doc.maturity_to){
			// frm.set_value("maturity_to", frm.doc.maturity_from);
			frappe.msgprint("'Maturity To' date should be greater than or equal to 'Maturity From' date");
		}
		if (frm.doc.booking_date > frm.doc.maturity_from){
			// frm.set_value("maturity_to", frm.doc.maturity_from);
			frappe.msgprint("'Maturity From' date should be greater than or equal to 'Booking Date' date");
		}
	},
	
	maturity_from: function(frm){
		// Set Maturity Date
		// frm.set_value("maturity_to", frm.doc.maturity_from);
		frm.trigger("date_validation");
		if(frm.doc.hedge == "Export"){
			if(frm.doc.maturity_from){
				let diffDays = frappe.datetime.get_diff(frm.doc.maturity_from, frm.doc.booking_date);
				frm.set_value('days_for_premium', diffDays);
			}
			else{
				let diffDays = frappe.datetime.get_diff(frm.doc.maturity_to, frm.doc.booking_date);
				frm.set_value('days_for_premium', diffDays);
			}
		}
		else if(frm.doc.hedge == "Import"){
			let diffDays = frappe.datetime.get_diff(frm.doc.maturity_to, frm.doc.booking_date);
			frm.set_value('days_for_premium', diffDays);

		}
	},
	
	maturity_to: function(frm){
		// Validate Maturity to date is > Maturity from
		frm.trigger("date_validation");
		if(frm.doc.hedge == "Export"){
			if(frm.doc.maturity_from){
				let diffDays = frappe.datetime.get_diff(frm.doc.maturity_from, frm.doc.booking_date);
				frm.set_value('days_for_premium', diffDays);
			}
			else{
				let diffDays = frappe.datetime.get_diff(frm.doc.maturity_to, frm.doc.booking_date);
				frm.set_value('days_for_premium', diffDays);
			}
		}
		else if(frm.doc.hedge == "Import"){
			let diffDays = frappe.datetime.get_diff(frm.doc.maturity_to, frm.doc.booking_date);
			frm.set_value('days_for_premium', diffDays);

		}
		
		frm.trigger("forward_booking_calculation");
	},
	
	can_avg_rate: function(frm){
		frm.trigger("calculate_rate_diff");
	},
	
	total_utilization: function(frm){
		frm.trigger("calculate_outstanding");
	},
	
	total_cancelled: function(frm){
		frm.trigger("calculate_outstanding");
	},
	
	amount: function(frm){
		frm.trigger("calculate_outstanding");
	},
	
	//Calculate Outstanding Amount
	calculate_outstanding: function(frm){
		let outstanding = flt(frm.doc.amount) - flt(frm.doc.total_utilization)-flt(frm.doc.total_cancelled);
		frm.set_value("amount_outstanding", outstanding);
	},
	
	//Calculate Cancellation Loss Profit
	calculate_rate_diff: function(frm){
		let rate_diff = 0.0;
		
		if (frm.doc.hedge == "Export"){
			rate_diff = flt(frm.doc.booking_rate) - flt(frm.doc.can_avg_rate);
		}
		else {
			rate_diff = flt(frm.doc.can_avg_rate) - flt(frm.doc.booking_rate);
		}
		frm.set_value("rate_diff", rate_diff);
		frm.set_value("diff_amount", rate_diff * flt(frm.doc.total_cancelled));
	},
	
	//Calculate INR Amount
	calculate_inramt: function(frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		let inramt = flt(d.cancel_amount) * flt(d.rate);
		frappe.model.set_value(cdt, cdn, "inr_amount", inramt);
	},
	
	//Calculate Total Cancelled Amount & Average Rate
	cal_calcellation_details: function(frm){
		let total = 0.0;
		let inr_total = 0.0;
		
		frm.doc.cancellation_details.forEach(function(d) {
			total += flt(d.cancel_amount);
			inr_total += flt(d.inr_amount);
		});
		
		frm.set_value("total_cancelled", total);
		frm.set_value("can_avg_rate", inr_total/total);
	},

	current_rate: function(frm){
		frm.trigger("forward_booking_calculation");
	},

	premium: function(frm){
		frm.trigger("forward_booking_calculation");
	},

	margin: function(frm){
		frm.trigger("forward_booking_calculation");
	},

	forward_booking_calculation: function(frm){

		let booking_rate = flt(frm.doc.current_rate) + flt(frm.doc.premium) - flt(frm.doc.margin);
		frm.set_value("booking_rate", booking_rate);
		console.log(booking_rate)

		let days_for_limit_blocked = frappe.datetime.get_diff(frm.doc.maturity_to, frm.doc.booking_date);
		frm.set_value("days_for_limit_blocked", days_for_limit_blocked);

		let outstanding_inr = flt(frm.doc.amount) * flt(frm.doc.booking_rate);
		frm.set_value("outstanding_inr", outstanding_inr);

		if(frm.doc.days_for_limit_blocked <= 30){
			frm.set_value("margin_percentage", 4.5);
		}
		else if(frm.doc.days_for_limit_blocked <= 60){
			frm.set_value("margin_percentage", 7.60);
		}
		else if(frm.doc.days_for_limit_blocked <= 90){
			frm.set_value("margin_percentage", 8.78);
		}
		else if(frm.doc.days_for_limit_blocked <= 150){
			frm.set_value("margin_percentage", 10.19);
		}

		let forward_limit_inr = (frm.doc.outstanding_inr * frm.doc.margin_percentage) / 100;
		frm.set_value("forward_limit_inr", forward_limit_inr);

		let forward_limit_usd = (frm.doc.forward_limit_inr / frm.doc.booking_rate).toFixed(2);
		frm.set_value("forward_limit_usd", forward_limit_usd);

		let forward_limit_inr_mtm = ((frm.doc.forward_limit_constant - frm.doc.current_rate) * frm.doc.amount) + frm.doc.forward_limit_inr;
		frm.set_value("forward_limit_inr_mtm", forward_limit_inr_mtm);
	},
});

frappe.ui.form.on("Forward Booking Underlying", {
	document: function(frm, cdt, cdn) {
		// Fetching Sales Order Details
		let d = locals[cdt][cdn];
		frappe.run_serially([
			()=> frappe.db.get_value("Sales Order", d.document, ["grand_total", "delivery_date", "amount_hedged"]),
			(r) => {
				frappe.model.set_value(cdt, cdn, "order_amount", r.message.grand_total);
				frappe.model.set_value(cdt, cdn, "delivery_date", r.message.delivery_date);
				frappe.model.set_value(cdt, cdn, "amount_covered", r.message.amount_hedged);
			}
		]);
	},
	
	//Calculate Total Underlying
	amount_covered: function(frm, cdt, cdn){
		let total = 0.0;
		frm.doc.forward_booking_underlying.forEach(function(d) {
			total += flt(d.amount_covered);
		});
		frm.set_value("total_underlying", total);
	}
});

frappe.ui.form.on("Forward Booking Cancellation", {
	cancel_amount: function(frm, cdt, cdn){		
		frm.events.cal_calcellation_details(frm);
		frm.events.calculate_inramt(frm, cdt, cdn);
	},
	
	rate: function(frm, cdt, cdn){
		frm.events.calculate_inramt(frm, cdt, cdn);
	}, 
	
	inr_amount: function(frm, cdt, cdn){
		frm.events.cal_calcellation_details(frm);
	},
	create_jv: function(frm, cdt, cdn){
		const d = locals[cdt][cdn];
		frappe.call({
			method: 'create_jv',
			doc: frm.doc,
			args: {
				row: d.name
			},
			callback: function(r){
				if(!r.exc){
					frm.reload_doc();
				}
			}
		})
	},
	cancel_jv: function(frm, cdt, cdn){
		const d = locals[cdt][cdn];
		frappe.call({
			method: 'cancel_jv',
			doc: frm.doc,
			args: {
				row: d.name
			},
			callback: function(r){
				if(!r.exc){
					frm.reload_doc();
				}
			}
		})
	}
});