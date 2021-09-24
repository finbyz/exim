

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

frappe.ui.form.on("Delivery Note", {
    before_save: function (frm) {
        frm.trigger("cal_total");
        frm.trigger("box_cal");
        frm.trigger('calculate_total_fob_value');
        frm.trigger('cal_igst_amount');

        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frm.doc.items.forEach(function(d){
                    frappe.model.set_value(d.doctype, d.name, "fob_value", flt(d.base_amount - d.freight - d.insurance));
                })
            }
        })
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
            }, __("Get items from"));
        }
    },
    cal_total: function (frm) {
        let total_qty = 0.0;
        let total_packages = 0;
        let total_gr_wt = 0.0;
        let total_tare_wt = 0.0;
        let total_pallets = 0;
        let total_freight = 0.0;
        let total_insurance = 0.0;


        frm.doc.items.forEach(function (d) {
            //frappe.model.set_value(d.doctype, d.name, 'gross_wt', (d.tare_wt + d.qty));
            total_qty += flt(d.qty);
            total_packages += flt(d.no_of_packages);
            d.total_tare_weight = flt(d.tare_wt * d.no_of_packages);
            d.gross_wt = flt(d.total_tare_weight) + flt(d.qty);
            total_tare_wt += flt(d.total_tare_weight);
            total_gr_wt += flt(d.gross_wt);
            total_pallets += flt(d.total_pallets);
            total_freight += flt(d.freight);
            total_insurance += flt(d.insurance);
        });
        frm.set_value("total_qty", total_qty);
        frm.set_value("total_packages", total_packages);
        frm.set_value("total_gross_wt", total_gr_wt);
        frm.set_value("total_tare_wt", total_tare_wt);
        frm.set_value("total_pallets", total_pallets);
        frm.set_value("freight", total_freight);
        frm.set_value("insurance", total_insurance);
    },
    box_cal: function (frm) {
        frm.doc.items.forEach(function (d, i) {
            if (i == 0) {
                d.packages_from = 1;
                d.packages_to = flt(d.no_of_packages);
            }
            else {
                d.packages_from = Math.round(frm.doc.items[i - 1].packages_to + 1);
                d.packages_to = Math.round(d.packages_from + d.no_of_packages - 1);
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
    cal_igst_amount: function (frm) {
        let total_igst = 0.0;
       
        if (frm.doc.currency != "INR") {
            frm.doc.items.forEach(function (d) {
                if (d.igst_rate) {
                    frappe.model.set_value(d.doctype, d.name, 'igst_amount', d.base_amount * parseInt(d.igst_rate) / 100);
                } else {
                    frappe.model.set_value(d.doctype, d.name, 'igst_amount', 0.0);
                }
                total_igst += flt(d.igst_amount);
            });
            frm.set_value('total_igst_amount', total_igst);
        }
    },
    duty_drawback_cal: function (frm) {
        let total_dt = 0;
        if (frm.doc.currency != "INR") {
            frm.doc.items.forEach(function (d) {
                frappe.model.set_value(d.doctype, d.name, "duty_drawback_amount", flt(d.fob_value * d.duty_drawback_rate / 100));
                total_dt += flt(d.duty_drawback_amount);
            });
            frm.set_value("total_duty_drawback", total_dt);
        }
    },
    calculate_total_fob_value: function (frm) {
        let total_fob_value = 0;
        if (frm.doc.currency != "INR") {
            frm.doc.items.forEach(function (d) {
                total_fob_value += flt(d.fob_value);
            });
            frm.set_value("total_fob_value", flt(total_fob_value - (frm.doc.freight * frm.doc.conversion_rate) - (frm.doc.insurance * frm.doc.conversion_rate)));
        }
    },
});
frappe.ui.form.on("Delivery Note Item", {
    qty: function (frm, cdt, cdn) {
        //EXIM
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
    // packaging_material: function (frm, cdt, cdn) {
    //     let d = locals[cdt][cdn];
    //     if (d.packaging_material == "Box") {
    //         frappe.model.set_value(cdt, cdn, "tare_wt", "1.5");
    //     }
    //     else if (d.packaging_material == "Jumbo Bag") {
    //         frappe.model.set_value(cdt, cdn, "tare_wt", "2.5");
    //     }
    //     else if (d.packaging_material == "Drum") {
    //         frappe.model.set_value(cdt, cdn, "tare_wt", "17.5");
    //     }
    // },
    packing_size: function (frm, cdt, cdn) {
        // frm.events.cal_total(frm);
        let d = locals[cdt][cdn];
        if(d.qty > 0 && d.packing_size > 0){
        frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packing_size));
        }
    },
    pallet_size: function (frm, cdt, cdn) {
        frappe.run_serially([
            () => {
                let d = locals[cdt][cdn];
                frappe.model.set_value(cdt, cdn, "total_pallets", Math.round(d.qty / d.pallet_size));
            },
            () => {
                frm.events.pallet_cal(frm);
            }
        ]);
    },
    no_of_packages: function (frm, cdt, cdn) {
        frm.events.box_cal(frm);
    },
    base_amount: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
            }
        })
    },
    freight: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
            }
        })
    },
    insurance: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
            }
        })
    },
    duty_drawback_rate: function (frm, cdt, cdn) {
        frm.events.duty_drawback_cal(frm);
    },

    capped_amount: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        if (d.maximum_cap == 1) {
            if (frm.doc.currency != "INR") {
                if (d.capped_amount < d.duty_drawback_amount) {
                    frappe.model.set_value(cdt, cdn, "duty_drawback_amount", d.capped_amount);
                }
                frappe.model.set_value(cdt, cdn, "effective_rate", flt(d.capped_amount / d.fob_value * 100));
            }
        }
    },

    fob_value: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frm.events.duty_drawback_cal(frm);
        frm.events.calculate_total_fob_value(frm);
        frm.events.cal_igst_amount(frm);
        //frappe.model.set_value(cdt, cdn, "igst_taxable_value", d.fob_value);
    },

	/* igst_taxable_value: function(frm, cdt, cdn){
		frm.events.cal_igst_amount(frm);
	}, */

    igst_rate: function (frm, cdt, cdn) {
        frm.events.cal_igst_amount(frm);
    },
});