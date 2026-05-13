/* eslint-disable */
// rename this file from _test_[name] to test_[name] to activate
// and remove above this line

QUnit.test("test: Advance Authorisation License", function (assert) {
	let done = assert.async();
	let frm;

	// number of asserts
	assert.expect(1);

	frappe.run_serially([
		// insert a new Advance Authorisation License
		() =>
			frappe.tests.make("Advance Authorisation License", [
				{ key: "value" },
			]).then((r) => {
				frm = r;
			}),

		() => {
			assert.equal(frm.doc.key, "value");
		},

		() => done(),
	]);

});
