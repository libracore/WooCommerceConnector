# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from woocommerceconnector.woocommerce_requests import get_woocommerce_items
from frappe.utils import cint
from frappe import _
from woocommerceconnector.exceptions import woocommerceError
import requests.exceptions
from frappe.utils.fixtures import sync_fixtures

def execute():
	sync_fixtures("woocommerceconnector")
	frappe.reload_doctype("Item")

	woocommerce_settings = frappe.get_doc("woocommerce Settings")
	if not woocommerce_settings.enable_woocommerce or not woocommerce_settings.password:
		return

	try:
		woocommerce_items = get_item_list()
	except woocommerceError:
		print "Could not run woocommerce patch 'set_variant_id' for site: {0}".format(frappe.local.site)
		return

	if woocommerce_settings.woocommerce_url and woocommerce_items:
		for item in frappe.db.sql("""select name, item_code, woocommerce_id, has_variants, variant_of from tabItem
			where sync_with_woocommerce=1 and woocommerce_id is not null""", as_dict=1):

			if item.get("variant_of"):
				frappe.db.sql(""" update tabItem set woocommerce_variant_id=woocommerce_id
					where name = %s """, item.get("name"))

			elif not item.get("has_variants"):
				product = filter(lambda woocommerce_item: woocommerce_item['id'] == cint(item.get("woocommerce_id")), woocommerce_items)

				if product:
					frappe.db.sql(""" update tabItem set woocommerce_variant_id=%s
						where name = %s """, (product[0]["variants"][0]["id"], item.get("name")))

def get_item_list():
	try:
		return get_woocommerce_items()
	except (requests.exceptions.HTTPError, woocommerceError) as e:
		frappe.throw(_("Something went wrong: {0}").format(frappe.get_traceback()), woocommerceError)

