// Fill Port Charges from Import Export Charges (type Import) when Port is selected.
frappe.ui.form.on("Supplier Quotation", {
	port(frm) {
		if (frm.doc.docstatus !== 0 || !frm.doc.port) return;

		frappe.call({
			method: "exim.exim.utils.port_charges.get_import_port_charges",
			args: { port: frm.doc.port },
			freeze: true,
			freeze_message: __("Fetching port charges..."),
			callback(r) {
				const charges = r.message || [];
				if (!charges.length) {
					frappe.show_alert({
						message: __("No Import charges configured for port {0}", [frm.doc.port]),
						indicator: "orange",
					});
					return;
				}

				const populate = () => {
					frm.clear_table("port_charges");
					charges.forEach((d) => {
						const row = frm.add_child("port_charges");
						row.charge_type = d.charge_type;
						row.item_name = d.item_name;
						row.amount = flt(d.amount);
					});
					frm.refresh_field("port_charges");
					frappe.show_alert({
						message: __("Loaded {0} charge(s) for port {1}", [charges.length, frm.doc.port]),
						indicator: "green",
					});
				};

				const has_existing = (frm.doc.port_charges || []).some((r) => r.charge_type || flt(r.amount));
				if (has_existing) {
					frappe.confirm(
						__("Import Export Charges already exist. Replace them with charges for port <b>{0}</b>?", [frm.doc.port]),
						populate
					);
				} else {
					populate();
				}
			},
		});
	},
});
