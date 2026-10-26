frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		// Supplier Address Filter
		frm.set_query("supplier_address", function () {
			return {
				query: "frappe.contacts.doctype.address.address.address_query",
				filters: {
					link_doctype: "Supplier",
					link_name: frm.doc.supplier,
				},
			};
		});

		// Supplier Contact Filter
		frm.set_query("contact_person", function () {
			return {
				query: "frappe.contacts.doctype.contact.contact.contact_query",
				filters: {
					link_doctype: "Supplier",
					link_name: frm.doc.supplier,
				},
			};
		});

		// Shipping Address Filter
		frm.set_query("shipping_address", function () {
			return {
				query: "frappe.contacts.doctype.address.address.address_query",
				filters: {
					link_doctype: "Company",
					link_name: frm.doc.company,
				},
			};
		});

		// Billing Address Filter
		frm.set_query("billing_address", function () {
			return {
				query: "frappe.contacts.doctype.address.address.address_query",
				filters: {
					link_doctype: "Company",
					link_name: frm.doc.company,
				},
			};
		});
	},

	billing_address(frm) {
		if (frm.doc.billing_address) {
			return frappe.call({
				method:
					"frappe.contacts.doctype.address.address.get_address_display",
				args: {
					address_dict: frm.doc.billing_address,
				},
				callback(r) {
					if (r.message) {
						frm.set_value(
							"billing_address_display",
							r.message
						);
					}
				},
			});
		}
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "Closed") {
			frm.add_custom_button(
				__("Import Shipment"),
				function () {
					frappe.model.open_mapped_doc({
						method: "exim.exim.doctype.import_shipment.import_shipment.make_import_shipment",
						frm: frm
					});
				},
				__("Create")
			);
		}
	},
});