frappe.ui.form.on("Document Template", {
	setup(frm) {
		frm.set_query("document_type", "required_documents", function() {
			return {
				filters: {
					is_active: 1
				}
			};
		});
	}
});
