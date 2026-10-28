// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Import Export Charges", {
	setup(frm) {
		frm.set_query("service", "charges", function() {
			return {
				filters: {
					is_stock_item: 0
				}
			};
		});
	}
});
