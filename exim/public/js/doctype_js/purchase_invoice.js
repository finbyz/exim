frappe.ui.form.on("Purchase Invoice", {
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

		frappe.db
			.get_single_value(
				"Exim Settings",
				"use_advance_authorization_license_based_on_cas_no_of_item"
			)
			.then((data) => {
				frm.set_query(
					"advance_authorisation_license",
					"items",
					function (doc, cdt, cdn) {
						let d = locals[cdt][cdn];

						if (data) {
							return {
								query:
									"exim.exim.doctype.advance_authorisation_license.advance_authorisation_license.cas_number_details",
								filters: {
									cas_number: d.cas_number,
								},
							};
						}

						return {
							query:
								"exim.exim.doctype.advance_authorisation_license.advance_authorisation_license.license_query",
							filters: {
								item_code: d.item_code,
							},
						};
					}
				);
			});
	},

	before_submit(frm) {
		frm.doc.items.forEach((d) => {
			if (d.advance_authorisation_license) {
				if (d.qty > d.license_qty) {
					frappe.throw(
						__(
							`Row:${d.idx} Qty should be less than or equal to License Qty.`
						)
					);
				}
			}
		});
	},

	onload(frm) {
		if (frm.doc.supplier_address || frm.doc.shipping_address) {
			// One address can be empty: get_value then returns nothing and
			// r.country / d.country threw "Cannot read properties of undefined".
			const get_country = (address) =>
				address
					? frappe.db.get_value("Address", address, "country").then((res) => res?.message?.country)
					: Promise.resolve(null);

			Promise.all([
				get_country(frm.doc.supplier_address),
				get_country(frm.doc.shipping_address),
			]).then(([supplier_country, shipping_country]) => {
				const is_india = supplier_country === "India" || shipping_country === "India";
				frm.set_df_property("shipping_details", "hidden", is_india ? 1 : 0);
			});
		}
	},

	refresh(frm) {
		sync_import_shipment_from_po(frm);
	},

	import_shipment(frm) {
		if (frm.doc.import_shipment && frm.doc.items) {
			frm.doc.items.forEach(row => {
				if (!row.import_shipment || row.import_shipment !== frm.doc.import_shipment) {
					frappe.model.set_value(row.doctype, row.name, "import_shipment", frm.doc.import_shipment);
				}
			});
			frm.refresh_field("items");
		}
	},
});

frappe.ui.form.on("Purchase Invoice Item", {
	item_code(frm, cdt, cdn) {
		let d = locals[cdt][cdn];

		setTimeout(() => {
			frappe.model.set_value(cdt, cdn, "cif_value", d.amount);
		}, 1000);

		frappe.model.set_value(
			cdt,
			cdn,
			"advance_authorisation_license",
			""
		);
	},

	qty(frm, cdt, cdn) {
		let d = locals[cdt][cdn];

		frappe.model.set_value(
			cdt,
			cdn,
			"cif_value",
			flt(d.rate * d.qty)
		);
	},

	advance_authorisation_license(frm, cdt, cdn) {
		let d = locals[cdt][cdn];

		if (d.advance_authorisation_license) {
			frappe.call({
				method:
					"exim.exim.doctype.advance_authorisation_license.advance_authorisation_license.get_license_details",
				args: {
					aal: d.advance_authorisation_license,
					item_code: d.item_code,
				},
				callback(r) {
					if (r.message) {
						frappe.model.set_value(
							cdt,
							cdn,
							"license_qty",
							r.message.approved_qty
						);

						frappe.model.set_value(
							cdt,
							cdn,
							"license_remaining_qty",
							r.message.remaining_qty
						);

						// frappe.model.set_value(cdt, cdn, 'license_amount', r.message.approved_amount);
						// frappe.model.set_value(cdt, cdn, 'license_remaining_amount', r.message.remaining_amount);
					}
				},
			});
		} else {
			frappe.model.set_value(cdt, cdn, "license_qty", 0);
			frappe.model.set_value(
				cdt,
				cdn,
				"license_remaining_qty",
				0
			);
			frappe.model.set_value(cdt, cdn, "license_amount", 0);
			frappe.model.set_value(
				cdt,
				cdn,
				"license_remaining_amount",
				0
			);
		}
	},

	purchase_order(frm, cdt, cdn) {
		sync_import_shipment_from_po(frm);
	},

	items_add(frm, cdt, cdn) {
		if (frm.doc.import_shipment) {
			frappe.model.set_value(cdt, cdn, "import_shipment", frm.doc.import_shipment);
		}
	}
});

function sync_import_shipment_from_po(frm) {
	// import_shipment is "Allow on Submit", so this also works on submitted invoices (as before).
	// Only skip cancelled invoices, which cannot be updated.
	if (frm.doc.import_shipment || frm.doc.docstatus === 2) return;

	let po_name = null;
	(frm.doc.items || []).forEach(row => {
		if (row.purchase_order && !po_name) {
			po_name = row.purchase_order;
		}
	});

	if (po_name) {
		frappe.call({
			method: "exim.exim.utils.purchase_invoice.get_po_import_shipment",
			args: { purchase_order: po_name },
			callback: function (r) {
				if (r && r.message && !frm.doc.import_shipment) {
					frm.set_value("import_shipment", r.message);
				}
			}
		});
	}
}
