

// Shipping Address Filter
cur_frm.set_query("shipping_address_name", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
    };
});

// Customer Contact Filter
cur_frm.set_query("contact_person", function () {
    return {
        query: "frappe.contacts.doctype.contact.contact.contact_query",
        filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
    };
});
frappe.db.get_single_value('Exim Settings', 'use_advance_authorization_license_based_on_cas_no_of_item').then(function(data) {
    if (data) {
        cur_frm.fields_dict.items.grid.get_field("advance_authorisation_license").get_query = function (doc, cdt, cdn) {
            let d = locals[cdt][cdn];
                return {
                    filters: {
                        "cas_number": d.cas_number
                    }
                };
        };
    } else {
        cur_frm.fields_dict.items.grid.get_field("advance_authorisation_license").get_query = function (doc, cdt, cdn) {
            let d = locals[cdt][cdn];
            return {
                filters: {
                    "export_item": d.item_code,
                }
            };
        };
    }
});
frappe.ui.form.on("Delivery Note", {
    caclulate_total: function (frm) {
        let total_qty = 0;
        let total_packages = 0;
        let total_gross_wt = 0;
        let total_tare_wt = 0;
        let total_freight = 0;
        let total_insurance = 0;
        let total_fob_value = 0;
        let total_pallets = 0;

        frm.doc.items.forEach(function (d) {
            if (frm.doc.freight_calculated == "By Qty") {
                d.freight = frm.doc.freight * d.qty / frm.doc.total_qty;
                d.insurance = frm.doc.insurance * d.qty / frm.doc.total_qty;
            }
            else if (frm.doc.freight_calculated == "By Amount") {
                d.freight = frm.doc.freight * d.base_amount / frm.doc.base_total;
                d.insurance = frm.doc.insurance * d.base_amount / frm.doc.base_total;
            }
            
            d.total_tare_weight = d.tare_wt * d.no_of_packages;
            d.gross_wt = d.total_tare_weight + (d.qty * (flt(d.weight_per_unit) || 1));
            
            if ((frm.doc.gst_category == "Overseas") && (!frm.doc.manually_enter_fob_value)) {
                if (['CIF', 'CFR', 'CNF', 'CPT'].indexOf(cur_frm.doc.shipping_terms) != -1){
                    d.fob_value = d.base_amount - (d.freight * frm.doc.conversion_rate) - (d.insurance * frm.doc.conversion_rate);
                } else {
                    d.fob_value = d.base_amount;
                }
            }
            
            total_fob_value += flt(d.fob_value);
            total_qty += flt(d.qty);
            total_packages += flt(d.no_of_packages);
            total_tare_wt += flt(d.total_tare_weight);
            total_gross_wt += flt(d.gross_wt);
            total_freight += flt(d.freight);
            total_insurance += flt(d.insurance);
            total_pallets += flt(d.total_pallets);
        });

        frm.refresh_field("items");

        frm.set_value("total_qty", total_qty);
        frm.set_value("total_packages", total_packages);
        frm.set_value("total_gross_wt", total_gross_wt);
        frm.set_value("total_tare_wt", total_tare_wt);
        frm.set_value("total_pallets", total_pallets);
        if (!((frm.doc.freight_calculated == "By Qty") || (frm.doc.freight_calculated == "By Amount"))) {
            frm.set_value("freight", total_freight);
        }
        frm.set_value("insurance", total_insurance);
        frm.set_value("total_fob_value", total_fob_value);
    },
    duty_calculation: function (frm) {
        if (frm.doc.gst_category == "Overseas") {
            let total_dt = 0;
            frm.doc.items.forEach(function (d) {
                d.duty_drawback_amount = flt(d.fob_value * d.duty_drawback_rate / 100);
                total_dt += flt(d.duty_drawback_amount);
            });
            frm.refresh_field("items");
            frm.set_value("total_duty_drawback", total_dt);
        }
    },
    // meis_calculation: function (frm) {
    //     if (frm.doc.gst_category == "Overseas") {
    //         let total_meis = 0.0;
    //         frm.doc.items.forEach(function (d) {
    //             d.meis_value = flt(d.fob_value * d.meis_rate / 100.0);
    //             total_meis += flt(d.meis_value)
    //         });
    //         frm.refresh_field("items");
    //         frm.set_value("total_meis", total_meis);
    //     }
    // },
    run_all_calculation: function (frm) {
        frappe.run_serially([
            // () => frm.trigger("caclulate_total"),
            () => frm.trigger("duty_calculation"),
            // () => frm.trigger("meis_calculation"),
        ]);
    },
    before_save: function (frm) {
        frm.trigger("box_cal");
        frm.trigger("run_all_calculation");

        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frm.doc.items.forEach(function(d){
                    frappe.model.set_value(d.doctype, d.name, "fob_value", flt(d.base_amount - d.freight - d.insurance));
                })
            }
        })
    },
    manually_enter_fob_value: function(frm){
        frm.trigger("run_all_calculation");
    },
    freight: function(frm){
        frm.trigger("run_all_calculation");
    },
    freight_calculated: function(frm){
        frm.trigger("run_all_calculation");
    },
    insurance: function(frm){
        frm.trigger("run_all_calculation");
    },
    shipping_terms: function(frm){
        frm.trigger("run_all_calculation");
    },
    insurance_percentage: function(frm){
        frm.trigger("run_all_calculation");
    },
	onload:function(frm){
		if(frm.doc.customer_address || frm.doc.shipping_address_name){
			frappe.db.get_value("Address", frm.doc.customer_address, "country", function (r) {
				frappe.db.get_value("Address", frm.doc.shipping_address_name, "country", function (d) {
					if(r.country == "India" || d.country == "India"){
						cur_frm.set_df_property("shipping_details", "hidden", 1);
					}
					else{
						cur_frm.set_df_property("shipping_details", "hidden", 0);
					}
				});
			});
		}
	},
    refresh: function (frm) {
        if (frm.doc.docstatus === 0) {
            cur_frm.add_custom_button(__('Sales Invoice'), function () {
                erpnext.utils.map_current_doc({
                    method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note",
                    source_doctype: "Sales Invoice",
                    target: cur_frm,
                    date_field: 'posting_date',
                    setters: {
                        customer: cur_frm.doc.customer || undefined,
                    },
                    get_query_filters: {
                        docstatus: 1,
                        status: ["!=", "Closed"],
                        company: cur_frm.doc.company
                    }
                })
            }, __("Get Items From"));
        }
    },
    box_cal: function (frm) {
        frm.doc.items.forEach(function (d, i) {
            if (i == 0) {
                d.packages_from = 1;
                d.packages_to = flt(d.no_of_packages);
            }
            else {
                d.packages_from = Math.round(flt(frm.doc.items[i - 1].packages_to) + 1);
                d.packages_to = Math.round(flt(d.packages_from) + flt(d.no_of_packages) - 1);
            }
        });
        frm.refresh_field('items');
    },
    pallet_cal: function (frm) {
        frm.doc.items.forEach(function (d, i) {
            if (d.palleted) {
                if (i == 0) {
                    d.pallet_no_from = 1;
                    d.pallet_no_to = Math.round(d.total_pallets);
                }
                else {
                    d.pallet_no_from = Math.round(frm.doc.items[i - 1].pallet_no_to + 1);
                    d.pallet_no_to = Math.round(d.pallet_no_from + d.total_pallets - 1);
                }
            }
        });
        frm.refresh_field('items');
    },
});
frappe.ui.form.on("Delivery Note Item", {
    packing_size: function (frm, cdt, cdn) {
        // frm.events.cal_total(frm);
        let d = locals[cdt][cdn];
        if(d.qty > 0 && d.packing_size > 0){
        frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packing_size));
        }
    },
    // pallet_size: function (frm, cdt, cdn) {
    //     frappe.run_serially([
    //         () => {
    //             let d = locals[cdt][cdn];
    //             frappe.model.set_value(cdt, cdn, "total_pallets", Math.round(flt(d.qty) / flt(d.pallet_size)));
    //         },
    //         () => {
    //             frm.events.pallet_cal(frm);
    //         }
    //     ]);
    // },
    total_pallets: function (frm, cdt, cdn) {
        frappe.run_serially([
            () => {
                let d = locals[cdt][cdn];
                frappe.model.set_value(cdt, cdn, "pallet_size", Math.round(d.qty / d.total_pallets));
            },
            () => {
                frm.events.pallet_cal(frm);
            }
        ]);
    },
    no_of_packages: function (frm, cdt, cdn) {
        frm.events.box_cal(frm);
    },
    qty: function (frm, cdt, cdn) {

        frappe.run_serially([
            () => {
                let d = locals[cdt][cdn];
                frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
                    if (r.country != "India") {
                        frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
                    }
                })
                if(d.qty > 0 && d.packing_size > 0){
                    frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packing_size));
                }
                if(d.qty > 0 && d.pallet_size > 0){
                    frappe.model.set_value(cdt, cdn, "total_pallets", Math.round(d.qty / d.pallet_size));
                }
            },
            () => frappe.timeout(1),
            () => frm.events.run_all_calculation(frm),
        ]);
    },
    rate: function (frm, cdt, cdn) {
        frappe.run_serially([
            () => frappe.timeout(1),
            () => frm.events.run_all_calculation(frm),
        ]);
    },
    discount_amount: function (frm, cdt, cdn) {
        frappe.run_serially([
            () => frappe.timeout(1),
            () => frm.events.run_all_calculation(frm),
        ]);
    },
    discount_percentage: function (frm, cdt, cdn) {
        frappe.run_serially([
            () => frappe.timeout(1),
            () => frm.events.run_all_calculation(frm),
        ]);
    },
    items_remove: function (frm) {
        frappe.run_serially([
            () => frappe.timeout(1),
            () => frm.events.run_all_calculation(frm),
        ]);
    },
    freight: function (frm, cdt, cdn) {
        frm.events.run_all_calculation(frm);
    },
    insurance: function (frm, cdt, cdn) {
        frm.events.run_all_calculation(frm);
    },
    duty_drawback_rate: function (frm, cdt, cdn) {
        frm.events.run_all_calculation(frm);
    },
    meis_rate: function (frm, cdt, cdn) {
        frm.events.run_all_calculation(frm);
    },

    capped_amount: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        if (d.maximum_cap == 1) {
            if (frm.doc.currency != "INR") {
                if (d.capped_amount < d.duty_drawback_amount) {
                    frappe.model.set_value(cdt, cdn, "duty_drawback_amount", d.capped_amount);
                }
                frappe.model.set_value(cdt, cdn, "effective_rate", flt(flt(d.capped_amount) / flt(d.fob_value) * 100));
            }
        }
    },

    // fob_value: function (frm, cdt, cdn) {
    //     let d = locals[cdt][cdn];
    //     frm.events.duty_drawback_cal(frm);
    //     frm.events.calculate_total_fob_value(frm);
    //     // frm.events.cal_igst_amount(frm);
    //     //frappe.model.set_value(cdt, cdn, "igst_taxable_value", d.fob_value);
    // },

	/* igst_taxable_value: function(frm, cdt, cdn){
		frm.events.cal_igst_amount(frm);
	},

    igst_rate: function (frm, cdt, cdn) {
        frm.events.cal_igst_amount(frm);
    },
    */
});