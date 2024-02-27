frappe.ui.form.on("Customize Form", {
    refresh: function(frm) {
        cur_frm.fields_dict.fields.grid.grid_pagination.page_length = 1000;
        cur_frm.refresh_fields('fields');
    }
});

frappe.customize_form.save_customization = function (frm) {
	if (frm.doc.doc_type) {
		return frm.call({
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Saving Customization..."),
			btn: frm.page.btn_primary,
			method: "save_customization",
			callback: function (r) {
				if (!r.exc) {
					frm.reload_doc();
					frappe.customize_form.clear_locals_and_refresh(frm);
					frm.script_manager.trigger("doc_type");
				}
			},
		});
	}
};