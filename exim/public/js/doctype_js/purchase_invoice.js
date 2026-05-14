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
			frappe.db.get_value(
				"Address",
				frm.doc.supplier_address,
				"country",
				(r) => {
					frappe.db.get_value(
						"Address",
						frm.doc.shipping_address,
						"country",
						(d) => {
							if (
								r.country === "India" ||
								d.country === "India"
							) {
								frm.set_df_property(
									"shipping_details",
									"hidden",
									1
								);
							} else {
								frm.set_df_property(
									"shipping_details",
									"hidden",
									0
								);
							}
						}
					);
				}
			);
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
});