
// Supplier Address Filter
cur_frm.set_query("supplier_address", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Supplier", link_name: cur_frm.doc.supplier }
    };
});

// Supplier Contact Filter
cur_frm.set_query("contact_person", function () {
    return {
        query: "frappe.contacts.doctype.contact.contact.contact_query",
        filters: { link_doctype: "Supplier", link_name: cur_frm.doc.supplier }
    };
});

// Shipping Address Filter
cur_frm.set_query("shipping_address", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Company", link_name: cur_frm.doc.company }
    };
});

cur_frm.set_query("billing_address", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Company", link_name: cur_frm.doc.company }
    };
});
frappe.ui.form.on('Purchase Order', {
    billing_address: function (frm) {
        if (frm.doc.billing_address) {
            return frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.billing_address
                },
                callback: function (r) {
                    if (r.message)
                        frm.set_value("billing_address_display", r.message);
                }
            });
        }
    },
})

