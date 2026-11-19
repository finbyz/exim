// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// Adds "Container" to ERPNext's Serial / Batch selector dialog:
//  - extra "Container" column in the downloadable CSV template
//  - "Container" column in the dialog table (filled from the uploaded CSV, editable)
// Server side: exim/exim/utils/serial_batch_container.py (via override_whitelisted_methods).

(function () {
	const Selector = window.erpnext && erpnext.SerialBatchPackageSelector;
	if (!Selector || Selector.prototype.__exim_container_patched) return;

	const proto = Selector.prototype;
	proto.__exim_container_patched = true;

	const original_get_dialog_table_fields = proto.get_dialog_table_fields;
	proto.get_dialog_table_fields = function () {
		const fields = original_get_dialog_table_fields.call(this);
		const container_field = {
			fieldtype: "Link",
			options: "Container",
			fieldname: "container",
			label: __("Container"),
			in_list_view: 1,
			get_query: () => ({ filters: { enable: 1 } }),
		};

		// keep the hidden "name" field last
		const name_idx = fields.findIndex((f) => f.fieldname === "name");
		fields.splice(name_idx < 0 ? fields.length : name_idx, 0, container_field);
		return fields;
	};

	proto.download_csv_file = function () {
		let csvFileData = ["Serial No"];

		if (this.item.has_serial_no && this.item.has_batch_no) {
			csvFileData = ["Serial No", "Batch No", "Quantity"];
		} else if (this.item.has_batch_no) {
			csvFileData = ["Batch No", "Quantity"];
		}

		// ERPNext reads the first columns by position, so Container must stay last
		csvFileData.push("Container No");

		const method = `/api/method/erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle.download_blank_csv_template?content=${encodeURIComponent(
			JSON.stringify(csvFileData)
		)}`;
		const w = window.open(frappe.urllib.get_full_url(method));
		if (!w) {
			frappe.msgprint(__("Please enable pop-ups"));
		}
	};
})();
