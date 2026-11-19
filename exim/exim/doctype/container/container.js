// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Container", {
	enable(frm) {
		if (frm.doc.enable) {
			frm.set_value("disable", 0);
		}
	},
	disable(frm) {
		if (frm.doc.disable) {
			frm.set_value("enable", 0);
		}
	}
});
