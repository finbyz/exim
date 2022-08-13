frappe.listview_settings['BRC Management'] = {
	get_indicator: function(doc) {
		if(doc.docstatus == 0) {
			return [__("Open"), "red", "status,=,Open"];
        } else if(doc.status ==="Open"){
            return [__("Open"), "red", "status,=,Open"];
        }else if(doc.status ==="Partially BRC Generated"){
			return [__("Partially BRC Generated"), "orange", "status,=,Partially BRC Generated"];
        } else if(doc.status ==="Completed"){
			return [__("Completed"), "green", "status,=,Completed"];
        }
	}
}

