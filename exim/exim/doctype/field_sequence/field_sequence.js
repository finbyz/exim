// Copyright (c) 2023, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt


frappe.ui.form.on('Field Sequence', {
	refresh: function(frm) {
		cur_frm.fields_dict.field_sequence_table.grid.grid_pagination.page_length = 500;
		cur_frm.refresh_fields('field_sequence_table');
		if (frm.doc.doc_type) {
			// Fetch and set fields when the DocType is changed
			fetchAndSetFields(frm);
		}
		frm.add_custom_button(__('Fetch Custom Field'), function () {
			if (frm.doc.doc_type) {
				frm.clear_table('field_sequence_table')
				fetchAllAndSetFields(frm);
			} else {
				frappe.msgprint("Please select the DocType")
			}
		});
	},
	doc_type: function(frm) {
		// Fetch and set fields when the DocType is changed
		fetchAndSetFields(frm);
	}
});

frappe.ui.form.on('Field Sequence Table', {
	field_sequence_table_add: function(frm, cdt, cdn) {
		// Fetch and set fields when a new row is added to the child table
		fetchAndSetFields(frm, cdt, cdn);
	}
});

function fetchAndSetFields(frm, cdt, cdn) {
	// Get the selected DocType
	let selectedDocType = frm.doc.doc_type;

	// Fetch the fields of the selected DocType
	frappe.model.with_doctype(selectedDocType, function() {
		let fields = frappe.get_meta(selectedDocType).fields;

		// Extract Section Break and Column Break field names
		let sectionBreakFieldNames = [];
		let columnBreakFieldNames = [];

		// Extract other field names for child table
		let childTableFields = [];

		fields.forEach(function(field) {
			if (field.fieldtype === 'Section Break') {
				sectionBreakFieldNames.push(field.fieldname);
			} else if (field.fieldtype === 'Column Break') {
				columnBreakFieldNames.push(field.fieldname);
			} 
			if (field.is_custom_field) {
				childTableFields.push({fieldname: field.fieldname, idx: field.idx});
			}
		});

		// Sort childTableFields based on idx
		childTableFields.sort(function(a, b) {
			return a.idx - b.idx;
		});

		// Extract fieldnames from the sorted array
		let sortedChildTableFieldNames = childTableFields.map(function(field) {
			return field.fieldname;
		});

		// Set the options for the Select field in the parent form
		frm.set_df_property("add_fields_before_section", "options", [""].concat(sectionBreakFieldNames, columnBreakFieldNames));

		// Set the options for the Select field in the child table
		frm.fields_dict.field_sequence_table.grid.update_docfield_property(
				"field_name",
				"options",
				[""].concat(sortedChildTableFieldNames)
			);

	});
}


function fetchAllAndSetFields(frm, cdt, cdn) {
	// Get the selected DocType
	let selectedDocType = frm.doc.doc_type;

	// Fetch the fields of the selected DocType
	frappe.model.with_doctype(selectedDocType, function() {
		let fields = frappe.get_meta(selectedDocType).fields;

		// Extract Section Break and Column Break field names
		let sectionBreakFieldNames = [];
		let columnBreakFieldNames = [];

		// Extract other field names for child table
		let childTableFields = [];

		fields.forEach(function(field) {
			if (field.fieldtype === 'Section Break') {
				sectionBreakFieldNames.push(field.fieldname);
			} else if (field.fieldtype === 'Column Break') {
				columnBreakFieldNames.push(field.fieldname);
			} 
			if (field.is_custom_field) {
				childTableFields.push({fieldname: field.fieldname, idx: field.idx});
			}
		});

		// Sort childTableFields based on idx
		childTableFields.sort(function(a, b) {
			return a.idx - b.idx;
		});

		// Extract fieldnames from the sorted array
		let sortedChildTableFieldNames = childTableFields.map(function(field) {
			return field.fieldname;
		});

		// Set the options for the Select field in the parent form
		frm.set_df_property("add_fields_before_section", "options", [""].concat(sectionBreakFieldNames, columnBreakFieldNames));

		// Set the options for the Select field in the child table
		frm.fields_dict.field_sequence_table.grid.update_docfield_property(
				"field_name",
				"options",
				[""].concat(sortedChildTableFieldNames)
			);


		for (var i = 0; i < sortedChildTableFieldNames.length; i++) {
			var row = cur_frm.add_child("field_sequence_table");
			row.field_name = sortedChildTableFieldNames[i];
		}
		
		cur_frm.refresh_fields("field_sequence_table");

	});
}