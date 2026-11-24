// Copyright (c) 2026, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Container and Shipment Wise PNL"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date (ETA)"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date (ETA)"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "import_shipment",
			label: __("Import Shipment"),
			fieldtype: "Link",
			options: "Import Shipment",
			get_query: () => {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: company ? { company } : {} };
			},
		},
		{
			fieldname: "container",
			label: __("Container"),
			fieldtype: "Link",
			options: "Container",
		},
		{
			fieldname: "view",
			label: __("View"),
			fieldtype: "Select",
			options: ["Container Wise", "Shipment Wise"],
			default: "Container Wise",
		},
		{
			fieldname: "show_batches",
			label: __("Show Batches"),
			fieldtype: "Check",
			default: 0,
		},
	],

	// T format: Expenses | Amount | Income | Amount, one block per container / shipment
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		const left = ["expense", "expense_amount"].includes(column.fieldname);
		const is_label = ["expense", "income"].includes(column.fieldname);

		switch (data.row_type) {
			case "gap":
				return "";
			case "title":
				return `<b style="color:var(--text-color)">${value || ""}</b>`;
			case "side_head":
				return is_label ? `<b style="text-transform:uppercase;letter-spacing:.4px">${value}</b>` : "";
			case "total":
				return `<b>${value}</b>`;
		}

		const indent = left ? data.l_indent : data.r_indent;
		const bold = left ? data.l_bold : data.r_bold;
		const kind = left ? data.l_kind : data.r_kind;
		const label = left ? data.expense : data.income;
		if (!label) return "";

		if (is_label && indent) value = `<span style="padding-left:${indent * 18}px">${value}</span>`;
		if (indent > 1) value = `<span style="color:var(--text-muted)">${value}</span>`;
		if (kind === "profit") value = `<span style="color:var(--green-600)">${value}</span>`;
		if (kind === "loss") value = `<span style="color:var(--red-600)">${value}</span>`;
		if (bold) value = `<b>${value}</b>`;
		return value;
	},
};
