//EXIM
cur_frm.add_fetch('advance_authorisation_license', 'approved_qty', 'license_qty');
cur_frm.add_fetch('advance_authorisation_license', 'remaining_export_qty', 'license_remaining_qty');
cur_frm.add_fetch('advance_authorisation_license', 'approved_amount', 'license_amount');
cur_frm.add_fetch('advance_authorisation_license', 'remaining_export_amount', 'license_remaining_amount');

// Address Filter
cur_frm.set_query("notify_party", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
    };
});

cur_frm.set_query("custom_consignee_address", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
    };
});
cur_frm.fields_dict.custom_address.get_query = function (doc) {
    return {
        filters: [
            ["address_type", "in", ["Consignee-Custom", "Custom"]],
            ["link_name", "=", cur_frm.doc.customer]
        ]
    }
};
// cur_frm.fields_dict.custom_buyer_address.get_query = function (doc) {
//     return {
//         filters: [
//             ["address_type", "in", ["Custom-buyer",'Custom']],
//             ["link_name", "=", cur_frm.doc.customer]
//         ]
//     }
// };


cur_frm.fields_dict.items.grid.get_field("advance_authorisation_license").get_query = function (doc, cdt, cdn) {
    let d = locals[cdt][cdn];
    return {
        filters: {
            "export_item": d.item_code,
        }
    }
};


/* cur_frm.fields_dict.supplier_transporter.get_query = function(doc) {
	return {
		filters: {
			"supplier_type": "Transporter"
		}
	}
}; */
// Customer Address Filter
cur_frm.set_query("customer_address", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: {
            link_doctype: "Customer",
            link_name: cur_frm.doc.customer
        }
    };
});
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

frappe.ui.form.on("Sales Invoice", {
    onload: function (frm) {
        // frm.trigger("set_package");
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
        var so_list_item = [];
        frm.doc.items.forEach(function (d) {
            if (d.sales_order) {
                so_list_item.push(d.sales_order)
            }
        })
        if (so_list_item.length) {
            frm.set_query("contract_and_lc", function () {
                return {
                    query: "exim.api.contract_and_lc_filter",
                    filters: {
                        'sales_order_item': so_list_item
                    }
                }
            })
        }
    },
    contract_and_lc: function (frm) {
        if (frm.doc.contract_and_lc) {
            frappe.model.with_doc("Contract Term", frm.doc.contract_and_lc, function () {
                var doc = frappe.model.get_doc("Contract Term", frm.doc.contract_and_lc)

                frm.clear_table('sales_invoice_export_document_item')
                $.each(doc.document || [], function (i, d) {
                    let c = frm.add_child('sales_invoice_export_document_item')
                    c.contract_term = doc.name;
                    c.export_document = d.export_document
                    c.number = d.number
                    c.copy = d.copy
                })

                frm.clear_table('sales_invoice_contract_term_check')
                $.each(doc.contract_term_check || [], function (i, d) {
                    let c = frm.add_child('sales_invoice_contract_term_check')
                    c.contract_term = doc.name;
                    c.document_check = d.document_check
                })

                frm.refresh_field('sales_invoice_export_document_item')
                frm.refresh_field('sales_invoice_contract_term_check')
            });
        }
        // frm.trigger("get_details_of_lc");
    },
    bl_date: function(frm){
        frm.trigger('maturity_date')
    },
    maturity_date: function (frm) {
        // frappe.db.get_value("Contract Term", frm.doc.contract_and_lc, "payment_term", function (r) {
            frappe.db.get_value("Payment Term", frm.doc.payment_schedule[0].payment_term, "credit_days", function (n) {
                frm.set_value("maturity_date", frappe.datetime.add_days(frm.doc.bl_date, n.credit_days));
            });
        // });
    },
    // custom_buyer_address: function (frm) {
    //     if (cur_frm.doc.custom_address) {
    //         return frappe.call({
    //             method: "frappe.contacts.doctype.address.address.get_address_display",
    //             args: {
    //                 "address_dict": frm.doc.custom_buyer_address
    //             },
    //             callback: function (r) {
    //                 if (r.message) {

    //                     frm.set_value("custom_buyer_address_display", r.message);
    //                 }
    //             }
    //         });
    //     }
    // },
	/* get_details_of_lc: function (frm) {
		frappe.db.get_value("Contract Term", frm.doc.contract_and_lc, ["marks_and_no", "no_and_kind_of_packages", "description_of_goods"], function (r) {
			if(r){
				frm.doc.items.forEach(function (d) {
					frappe.model.set_value(d.doctype, d.name, "marks_and_no", r.marks_and_no);
					frappe.model.set_value(d.doctype, d.name, "no_and_kind_of_packages", r.no_and_kind_of_packages);
					frappe.model.set_value(d.doctype, d.name, "description_of_goods", r.description_of_goods);
				});
			}
		});
    }, */
    before_save: function (frm) {
        frm.trigger("cal_total");
        // frm.trigger("box_cal");

        //EXIM
        // frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
        //     if (r.country != "India") {
        //         frm.doc.items.forEach(function(d){
        //             frappe.model.set_value(d.doctype, d.name, "fob_value", flt(d.base_amount - d.freight - d.insurance));
        //         })
        //     }
        // })
        frm.events.cal_igst_amount(frm);
        frm.trigger('calculate_total_fob_value');
        frm.trigger("duty_drawback_cal");
        frm.trigger("meis_cal");

        if (frm.doc.shipping_address_name == "") {
            frm.set_value("shipping_address_name", frm.doc.customer_address);
        }
        frm.refresh_field('items');
        frappe.db.get_value("Company", frm.doc.company, 'abbr', function (r) {
            if (frm.doc.is_opening == "Yes") {
                $.each(frm.doc.items || [], function (i, d) {
                    d.income_account = 'Temporary Opening - ' + r.abbr;
                });
            }
        });
        /*frm.doc.items.forEach(function (d) {
            if (!d.item_code) {
                frappe.throw("Please Select the item")
            }

            frappe.call({
                method: 'chemical.api.get_customer_ref_code',
                args: {
                    'item_code': d.item_code,
                    'customer': frm.doc.customer,
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(d.doctype, d.name, 'item_name', r.message);
                        //frappe.model.set_value(d.doctype, d.name, 'description', r.message);
                    }
                }
            })
        })*/
    },
    //EXIM
    customer: function (frm) {
        frappe.call({
            method: "exim.api.get_custom_address",
            args: {
                party: frm.doc.customer,
                party_type: "Customer"
            },
            callback: function (r) {
                if (r.message) {
                    frm.set_value("custom_address", r.message.customer_address);
                    frm.set_value("custom_address_display", r.message.address_display);
                }
            }
        });
    },
    notify_party: function (frm) {
        if (cur_frm.doc.notify_party) {
            return frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.notify_party
                },
                callback: function (r) {
                    if (r.message)
                        frm.set_value("notify_address_display", r.message);
                }
            });
        }
    },
    custom_consignee_address: function (frm) {
        if (cur_frm.doc.custom_consignee_address) {
            return frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.custom_consignee_address
                },
                callback: function (r) {
                    if (r.message)
                        frm.set_value("custom_consignee_address_display", r.message);
                }
            });
        }
    },
    custom_address: function (frm) {
        if (cur_frm.doc.custom_address) {
            return frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.custom_address
                },
                callback: function (r) {
                    if (r.message) {

                        frm.set_value("custom_address_display", r.message);
                    }
                }
            });
        }
    },
    cal_igst_amount: function (frm) {
        let total_igst = 0.0;
        frappe.model.get_value('Address', {"name":frm.doc.customer_address}, 'country',(res)=>{
            if(res.country != "India"){
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
        })
    },
    duty_drawback_cal: function (frm) {
        let total_dt = 0;
     
        frappe.model.get_value('Address', {"name":frm.doc.customer_address}, 'country',(res)=>{frm.doc.customer_address
            if(res.country != "India"){
            frm.doc.items.forEach(function (d) {
                frappe.model.set_value(d.doctype, d.name, "duty_drawback_amount", flt(d.fob_value * d.duty_drawback_rate / 100));
                total_dt += flt(d.duty_drawback_amount);
            });
            frm.set_value("total_duty_drawback", total_dt);
        }
        })
    },
    meis_cal: function(frm){
        let total_meis = 0.0;
        frappe.model.get_value('Address', {"name":frm.doc.customer_address}, 'country',(res)=>{
            if(res.country != "India"){
                frm.doc.items.forEach(function (d) {
                    frappe.model.set_value(d.doctype, d.name, "meis_value", flt(d.fob_value * d.meis_rate / 100.0));
                    total_meis += flt(d.meis_value)
                });
                let meta = frappe.get_meta('Sales Invoice')
                // if (meta.has_field('total_meis')){

                //     frm.set_value("total_meis", total_meis);
                // }
            } 
        })
    },
    calculate_total_fob_value: function (frm) {
        let total_fob_value = 0;
        frappe.model.get_value('Address', frm.doc.customer_address, 'country',(res)=>{
            if(res.country != "India"){
                frm.doc.items.forEach(function (d) {
                    if(frm.doc.fob_calculation){
                    frappe.model.set_value(d.doctype, d.name, "fob_value",flt(d.base_amount - flt(d.freight * frm.doc.conversion_rate ) - flt(d.insurance * frm.doc.conversion_rate)));
                    }
                    total_fob_value += flt(d.fob_value);
                });
               
                frm.set_value("total_fob_value", flt(total_fob_value - flt(frm.doc.freight * frm.doc.conversion_rate) - flt(frm.doc.insurance * frm.doc.conversion_rate)));
          
            } 
        })
       
    },
    //EXIM END
    cal_total: function (frm) {
        let total_qty = 0;
        let total_packages = 0;
        let total_gr_wt = 0;
        let total_tare_wt = 0;
        let total_freight = 0;
        let total_insurance = 0;

        frm.doc.items.forEach(function (d) {
            //frappe.model.set_value(d.doctype, d.name, 'gross_wt', (d.tare_wt + d.qty));
            total_qty += flt(d.qty);
            total_packages += flt(d.no_of_packages);
            d.total_tare_weight = flt(d.tare_wt * d.no_of_packages);
            d.gross_wt = flt(d.total_tare_weight) + flt(d.qty);
            total_tare_wt += flt(d.total_tare_weight);
            total_gr_wt += flt(d.gross_wt);
            total_freight += flt(d.freight);
            total_insurance += flt(d.insurance);
        });
        frm.set_value("total_qty", total_qty);
        frm.set_value("total_packages", total_packages);
        frm.set_value("total_gr_wt", total_gr_wt);
        frm.set_value("total_tare_wt", total_tare_wt);
        frm.set_value("freight", total_freight);
        frm.set_value("insurance", total_insurance);
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
    },
});
frappe.ui.form.on("Sales Invoice Item", {
    
    qty: function (frm, cdt, cdn) {
        //EXIM
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value",flt(d.base_amount - flt(d.freight * frm.doc.conversion_rate ) - flt(d.insurance * frm.doc.conversion_rate)));
            }
        })
        if(d.qty > 0 && d.packing_size > 0){
            frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packing_size));
        }
        if(d.qty > 0 && d.pallet_size > 0){
            frappe.model.set_value(cdt, cdn, "total_pallets", Math.round(d.qty / d.pallet_size));
        }
    },
    quantity: function(frm, cdt, cdn){
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value",flt(d.base_amount - flt(d.freight * frm.doc.conversion_rate ) - flt(d.insurance * frm.doc.conversion_rate)));

            }
        })
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
        // frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packing_size));
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
    //EXIM
    base_amount: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                console.log(flt(d.base_amount))
                console.log(flt(d.freight))
                console.log(flt(d.insurance))
                frappe.model.set_value(cdt, cdn, "fob_value",flt(d.base_amount - flt(d.freight * frm.doc.conversion_rate ) - flt(d.insurance * frm.doc.conversion_rate)));

            }
        })
    },
    freight: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value",flt(d.base_amount - flt(d.freight * frm.doc.conversion_rate ) - flt(d.insurance * frm.doc.conversion_rate)));

            }
        })
    },
    insurance: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value",flt(d.base_amount - flt(d.freight * frm.doc.conversion_rate ) - flt(d.insurance * frm.doc.conversion_rate)));

            }
        })
    },
    duty_drawback_rate: function (frm, cdt, cdn) {
        frm.events.duty_drawback_cal(frm);
    },
    meis_rate: function (frm, cdt, cdn) {
        frm.events.meis_cal(frm);
    },
    capped_rate: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "capped_amount", flt(d.qty * d.capped_rate));
    },
    capped_amount: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        if (d.maximum_cap == 1) {
            frappe.model.get_value('Address', {"name":frm.doc.customer_address}, 'country',(res)=>{
                if(res.country != "India"){
                    if (d.capped_amount < d.duty_drawback_amount) {
                        frappe.model.set_value(cdt, cdn, "duty_drawback_amount", d.capped_amount);
                    }
                    frappe.model.set_value(cdt, cdn, "effective_rate", flt(d.capped_amount / d.fob_value * 100));
                } 
            })
          
        }
    },

    fob_value: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frm.events.duty_drawback_cal(frm);
        frm.events.calculate_total_fob_value(frm);
        let meta = frappe.get_meta(frm.doc.doctype)
        // if(meta.has_field('meis_cal')){

        //     frm.events.meis_cal(frm);
        // }
        // frm.events.cal_igst_amount(frm);
        //frappe.model.set_value(cdt, cdn, "igst_taxable_value", d.fob_value);
    },

	/* igst_taxable_value: function(frm, cdt, cdn){
		frm.events.cal_igst_amount(frm);
	}, */

    igst_rate: function (frm, cdt, cdn) {
        frm.events.cal_igst_amount(frm);
    },
});

frappe.ui.form.on('Notify Party Address', {
	notify_party: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
		if (d.notify_party) {
			return frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					"address_dict": d.notify_party
				},
				callback: function (r) {
					if (r.message)
					frappe.model.set_value(cdt, cdn,"notify_address_display", r.message);
				}
			});
		}else{
			frappe.model.set_value(cdt, cdn,"notify_address_display", " ");
		}
		
	}
})



// rodtep_claim_management app code
function calculate_total_fob_value_1(frm, cdt, cdn){
		
	let d=locals[cdt][cdn]
	if(frm.doc.currency=='INR'){
	frappe.model.set_value(cdt,cdn,'fob_value',d.base_amount-(d.insurance+d.freight))
	frappe.model.set_value(cdt,cdn,'fob_value_inr',d.base_amount-(d.insurance+d.freight))
	frappe.model.set_value(cdt,cdn,'duty_drawback_amount',d.fob_value_inr*d.duty_drawback_rate/100)
	frappe.model.set_value(cdt,cdn,'meis_value',d.fob_value_inr*d.meis_rate/100)
	}
	if(frm.doc.currency != 'INR'){
	frappe.model.set_value(cdt,cdn,'fob_value',d.amount-(d.freight+d.insurance))
	frappe.model.set_value(cdt,cdn,'fob_value_inr',d.base_amount-(d.freight*frm.doc.conversion_rate+frm.doc.conversion_rate*d.insurance)) 
	frappe.model.set_value(cdt,cdn,'duty_drawback_amount',d.fob_value_inr*d.duty_drawback_rate/100)
	frappe.model.set_value(cdt,cdn,'meis_value',d.fob_value_inr*d.meis_rate/100)
}

}
frappe.ui.form.on('Sales Invoice Item',{
	
			 freight:function(frm,cdt,cdn){
				
				calculate_total_fob_value_1(frm, cdt, cdn)
			 },
			 insurance:function(frm,cdt,cdn){
				
				calculate_total_fob_value_1(frm, cdt, cdn)
			 },
			 duty_drawback_rate:function(frm,cdt,cdn){
				
				calculate_total_fob_value_1(frm, cdt, cdn)
			 },
			 meis_rate:function(frm,cdt,cdn){
				
				calculate_total_fob_value_1(frm, cdt, cdn)
			 },
			
})
