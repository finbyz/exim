// frappe.ui.form.on("Purchase Receipt", {
// 	before_save: function(frm){
// 		frm.trigger('cal_qty');
// 	},
// 	cal_qty: function(frm){
// 		let rec_qty = 0;
// 		frm.doc.items.forEach(function(d){
// 			if(d.item_group == "Raw Material"){
// 				rec_qty = (flt(d.packing_size)*flt(d.no_of_packages)*flt(d.concentration))/100;
// 			}
// 			else{
// 				rec_qty = (flt(d.packing_size)*flt(d.no_of_packages));
// 			}
// 				frappe.model.set_value(d.doctype,d.name,"received_qty",rec_qty);
// 				frappe.model.set_value(d.doctype,d.name,"qty",rec_qty);
			
// 		});
// 	}
// });

// frappe.ui.form.on("Purchase Receipt Item", {
// 	packing_size: function(frm, cdt, cdn){
// 		frm.events.cal_qty(frm);
// 	},
// 	no_of_packages: function(frm, cdt, cdn){
// 		frm.events.cal_qty(frm);
// 	},
// });