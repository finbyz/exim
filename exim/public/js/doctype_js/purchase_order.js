
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