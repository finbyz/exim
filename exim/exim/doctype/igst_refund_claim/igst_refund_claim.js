// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

// frappe.ui.form.on("IGST Refund Claim", {
// 	refresh(frm) {

// 	},
// });

// Copyright (c) 2022, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("IGST Refund Claim", {
	get_igst_refund_entries(frm) {
		if (frm.doc.igst_refund_details) {
			for (let j = frm.doc.igst_refund_details.length - 1; j >= 0; j--) {
				frm.get_field("igst_refund_details").grid.grid_rows[j].remove();
			}
		}

		frappe.call({
			method:
				"exim.exim.doctype.igst_refund_claim.igst_refund_claim.journal_entry_list",
			args: {
				start_date: frm.doc.start_date,
				end_date: frm.doc.end_date,
				company: frm.doc.company,
			},
			callback: function (r) {
				if (r.message) {
					r.message.forEach(function (res) {
						let childTable = frm.add_child("igst_refund_details");

						childTable.je_no = res.je_no;
						childTable.shipping_bill_no = res.shipping_bill_no;
						childTable.account = res.account;
						childTable.debit_amount = res.debit_amount;
						childTable.cheque_date = res.cheque_date;
						childTable.cheque_no = res.cheque_no;
					});
				} else {
					frm.doc.igst_refund_details = [];
				}

				frm.refresh_field("igst_refund_details");
			},
		});
	},

	refresh(frm) {
		frm.set_query("credit_account", function () {
			return {
				filters: {
					is_group: 0,
				},
			};
		});
	},
});