this.frm.cscript.onload = function (frm) {

    // Billing Address Filter
    this.frm.set_query("customer_address", function () {
        return {
            query: "frappe.contacts.doctype.address.address.address_query",
            filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
        };
    });

    // Shipping Address Filter
    this.frm.set_query("shipping_address_name", function () {
        return {
            query: "frappe.contacts.doctype.address.address.address_query",
            filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
        };
    });

    // Supplier Contact Filter
    this.frm.set_query("contact_person", function () {
        return {
            query: "frappe.contacts.doctype.contact.contact.contact_query",
            filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
        };
    });
    // this.frm.fields_dict.items.grid.get_field("ref_no").get_query = function (doc) {
    //     return {
    //         filters: {
    //             "product_name": doc.items.item_code,
    //         }
    //     }
    // };
    cur_frm.fields_dict.items.grid.get_field("ref_no").get_query = function (doc, cdt, cdn) {
        let d = locals[cdt][cdn];
        return {
            filters: {
                "product_name": d.item_code,
            }
        }
    };

}
frappe.ui.form.on("Sales Order", {
    before_save: function (frm) {
        frm.trigger("cal_total");
        // frm.trigger("box_cal");
        frappe.call({
            method: 'exim.api.company_address',
            args: {
                'company': frm.doc.company
            },
            callback: function (r) {
                if (r.message && frm.doc.__islocal) {
                    frm.set_value("company_address", r.message.company_address);
                }
            }
        })
    },
    refresh: function (frm) {
        if (!in_list(["Closed", "Completed"], frm.doc.status)) {
            if (frm.doc.docstatus == 1) {
                frm.add_custom_button(__("LC"), function () {
                    frappe.model.open_mapped_doc({
                        method: "exim.api.make_lc",
                        frm: cur_frm
                    })
                }, __("Make"))
            }

        }
		
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
	onload_post_render: function(frm){
		// hide delivery note from make button
		let $group = cur_frm.page.get_inner_group_button("Make");
		
		let li_length = $group.find("ul li");
		for (let i = 0; i < li_length.length -1; i++) {		
			var li = $group.find(".dropdown-menu").children("li")[i];
			if (li.getElementsByTagName("a")[0].innerHTML == "Delivery")
				$group.find(".dropdown-menu").children("li")[i].remove();
		}
	},
    cal_total: function (frm) {
        let total_qty = 0.0;
        let total_gr_wt = 0.0;
        let total_packages = 0.0;

        frm.doc.items.forEach(function (d) {
            total_qty += flt(d.qty);
            total_gr_wt += flt(d.gross_wt);
            total_packages += flt(d.no_of_packages);
        });

        frm.set_value("total_qty", total_qty);
        frm.set_value("total_gr_wt", total_gr_wt);
        frm.set_value("total_packages", total_packages);
    },
    box_cal: function (frm) {
        frm.doc.items.forEach(function (d, i) {
            if (i == 0) {
                d.packages_from = 1;
                d.packages_to = d.no_of_packages;
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
    }
});
frappe.ui.form.on("Sales Order Item", {
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
    qty: function (frm, cdt, cdn) {
        //EXIM
        let d = locals[cdt][cdn];
        if(d.qty > 0 && d.packing_size > 0){
            frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packing_size));
        }
    },
    packing_size: function (frm, cdt, cdn) {
        // frm.events.cal_total(frm);
        let d = locals[cdt][cdn];
        if (d.qty > 0 && d.packing_size > 0){
            frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packing_size));
        }
    },
    no_of_packages: function (frm, cdt, cdn) {
        frm.events.box_cal(frm);
        frm.events.cal_total(frm);
    },

});