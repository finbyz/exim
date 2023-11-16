// Copyright (c) 2022, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Duty DrawBack Claim', {
	get_rodtep_entries:function(frm){
		if (frm.doc.rodtep_details) {
            for (var j = frm.doc.rodtep_details.length - 1; j >= 0; j--) {
                cur_frm.get_field("rodtep_details").grid.grid_rows[j].remove();
            }
        }
		frappe.call({
			method : "exim.exim.doctype.duty_drawback_claim.duty_drawback_claim.journal_entry_list",
			args:{
				"start_date":frm.doc.start_date,
				"end_date":frm.doc.end_date,
				"company":frm.doc.company
			},
			callback: function(r) {
				if(r.message){
				r.message.forEach(function(res) {
					var childTable = cur_frm.add_child("rodtep_details");
					childTable.je_no = res['je_no']
					childTable.shipping_bill_no = res['shipping_bill_no']
					childTable.account = res['account']
					childTable.debit_amount = res['debit_amount']
					childTable.cheque_date = res['cheque_date']
					childTable.cheque_no = res['cheque_no']
				})
			}
				else{
					cur_frm.doc.rodtep_details = []
	
				}
					// cur_frm.refresh();
					cur_frm.refresh_field("rodtep_details")
						
					
				
			}

		});
		
	},
	refresh:function(frm){
		frm.set_query("credit_account", function() {
			return {
				"filters": {
					
					"is_group": 0,
				}
			};
		});
	}
});