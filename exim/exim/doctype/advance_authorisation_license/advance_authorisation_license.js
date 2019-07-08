cur_frm.add_fetch("item_code", "license_name", "license_name");

let set_currency = 0;

frappe.ui.form.on("Advance Authorisation License",{
	approved_qty:function(frm) {
		var remaining_exp_qty = flt(frm.doc.approved_qty) - flt(frm.doc.total_export_qty);
		frm.set_value("remaining_export_qty", remaining_exp_qty);
	},
	
	approved_amount:function(frm){
		var remaining_exp_amount = flt(frm.doc.approved_amount) - flt(frm.doc.total_export_amount);
		frm.set_value("remaining_export_amount", remaining_exp_amount);
	},
	onload: function(frm){
		if(frm.doc.__islocal) {
			frm.doc.item_import_ratio.forEach(function(d) {
				frappe.model.set_value(d.doctype,d.name,"currency", "USD" );
			});
		}
	},
}); 


frappe.ui.form.on("Item Import Ratio", {
	ratio: function(frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (d.ratio>1){
			frappe.throw(__("Ratio cannot be greater than 1"));
		}
		frappe.model.set_value(cdt, cdn, "approved_qty", flt(frm.doc.approved_qty * d.ratio));
		//frappe.model.set_value(cdt, cdn, "approved_amount", flt(frm.doc.approved_amount * d.ratio));
	},

	approved_qty: function(frm,cdt,cdn){
		let d = locals[cdt][cdn];
		if(frm.doc.approved_qty){
			frappe.model.set_value(cdt, cdn, "ratio",flt(d.approved_qty/frm.doc.approved_qty))
		}
	},
	item_import_ratio_add:function(frm , cdt, cdn){
		frappe.model.set_value(cdt,cdn,"currency", "USD" );
	},
	// currency: function(frm, cdt, cdn){
	// 	if(d.currency == 'INR' && !set_currency){
	// 		frappe.model.set_value(d.doctype,d.name,"currency", "USD" );
	// 		set_currency = 1;
	// 	}
	// },
});