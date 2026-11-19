frappe.ui.form.on("Document Template Mapping", {
	setup(frm) {
		frm.set_query("template", function() {
			return {
				filters: {
					is_active: 1
				}
			};
		});
		frm.set_query("target_doctype", function() {
			return {
				filters: {
					istable: 0,
					issingle: 0
				}
			};
		});
	},
	refresh(frm) {
		if (!frm.is_new() && frm.doc.target_doctype) {
			frm.add_custom_button(__("View Target DocType"), function() {
				frappe.set_route("List", frm.doc.target_doctype);
			});
		}
	}
});
