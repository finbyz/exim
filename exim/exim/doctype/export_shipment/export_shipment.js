// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Export Shipment", {
	setup(frm) {
		const supplier_group = (group) => () => ({ filters: { supplier_group: group } });
		frm.set_query("shipping_line", supplier_group("Shipping Line"));
		frm.set_query("cha", supplier_group("CHA"));

		frm.set_query("sales_order", () => ({
			filters: {
				docstatus: 1,
				status: ["not in", ["Closed", "On Hold"]],
				...(frm.doc.customer ? { customer: frm.doc.customer } : {}),
			},
		}));

		frm.set_query("notify_party", () =>
			frm.doc.customer
				? {
						query: "frappe.contacts.doctype.address.address.address_query",
						filters: { link_doctype: "Customer", link_name: frm.doc.customer },
				  }
				: {}
		);

		frm.set_query("item_code", "containers", () => ({ filters: { is_sales_item: 1 } }));
		frm.set_query("sales_invoice", "containers", () => ({
			filters: {
				docstatus: ["!=", 2],
				...(frm.doc.customer ? { customer: frm.doc.customer } : {}),
			},
		}));
		frm.set_query("charge_type", "charges", () => ({ filters: { is_stock_item: 0 } }));
		frm.set_query("purchase_invoice", "charges", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return { filters: { docstatus: 1, ...(row.supplier ? { supplier: row.supplier } : {}) } };
		});
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_user_default("Company") || "");
		}
	},

	refresh(frm) {
		add_final_costing_buttons(frm);
	},

	port_of_loading(frm) {
		const has_charges = (frm.doc.charges || []).some((row) => row.charge_type);
		if (!frm.doc.port_of_loading || has_charges) return;
		frappe.call({
			method: "exim.exim.doctype.export_shipment.export_shipment.get_export_port_charges",
			args: { port: frm.doc.port_of_loading },
			callback(r) {
				if (!(r.message || []).length) return;
				frm.clear_table("charges");
				r.message.forEach((c) => {
					const row = frm.add_child("charges");
					row.charge_type = c.charge_type;
					row.item_name = c.item_name;
					row.amount = c.amount;
				});
				frm.refresh_field("charges");
			},
		});
	},
});

frappe.ui.form.on("Export Shipment Container", {
	containers_add(frm, cdt, cdn) {
		// new container row starts with the previous row's type, item and invoice
		const rows = frm.doc.containers || [];
		const row = locals[cdt][cdn];
		const prev = rows[rows.indexOf(row) - 1];
		if (!prev) return;
		["container_type", "item_code", "item_name", "sales_invoice"].forEach((f) => {
			if (prev[f] && !row[f]) row[f] = prev[f];
		});
		frm.refresh_field("containers");
	},
});

// Status is set from the milestone dates on save. Final Costing is the one manual step.
function add_final_costing_buttons(frm) {
	if (frm.is_new() || frm.is_dirty()) return;
	const set_status = (status) => {
		frm.set_value("status", status);
		frm.save();
	};
	if (frm.doc.status === "Delivered") {
		frm.add_custom_button(__("Mark Final Costing"), () => set_status("Final Costing"));
	} else if (frm.doc.status === "Final Costing") {
		frm.add_custom_button(__("Reopen Costing"), () => set_status("Delivered"));
	}
}
