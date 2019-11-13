frappe.ui.form.on('Lead', { 
	refresh: function(frm) {
		frm.add_custom_button(__("Send Mail"), function() {
			let recipients = '';
            let person = '';

			if(frm.doc.organization_lead){
				frappe.call({
					method: "exim.get_party_details.get_party_details",
					args: {
						party: frm.doc.name,
						party_type: "Lead"
					},
					callback: function(r){
						if(r.message.contact_email){
							recipients = r.message.contact_email.toLowerCase();
							person = r.message.contact_display;
							send_email(recipients, person, frm.doc.group_company, frm.doc.email_template);
						}
						else{
							frappe.throw(__("No email address found in Contact. Please add email address in Contact."));
						}
					}
				});
			}
			else{
				if(frm.doc.email_id){
					recipients = frm.doc.email_id;
					person = frm.doc.lead_name;
					send_email(recipients, person, frm.doc.group_company, frm.doc.email_template);
				}
				else{
					frappe.throw(__("Please mention Email Address!"));
				}
			}
		})
	}
});

var send_email = function(recipients, person, group_company, email_template){
    console.log(recipients);
    console.log(person);
    console.log(group_company);
    console.log(email_template);
	frappe.call({
		method : "exim.api.send_lead_mail",
		args : {
			recipients: recipients,
			person: person,
			group_company: group_company,
			email_template: email_template
		},
		callback: function(r) {
			if(!r.exc){
				frappe.msgprint(r.message);
			}
		}
    });
};
