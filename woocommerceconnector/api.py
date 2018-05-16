# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from .exceptions import woocommerceError
from .sync_orders import sync_orders
from .sync_customers import sync_customers
from .sync_products import sync_products, update_item_stock_qty
from .utils import disable_woocommerce_sync_on_exception, make_woocommerce_log
from frappe.utils.background_jobs import enqueue

@frappe.whitelist()
def sync_woocommerce():
	"Enqueue longjob for syncing woocommerce"
	enqueue("woocommerceconnector.api.sync_woocommerce_resources", queue='long', timeout=1500)
	frappe.msgprint(_("Queued for syncing. It may take a few minutes to an hour if this is your first sync."))

@frappe.whitelist()
def sync_woocommerce_resources():
	woocommerce_settings = frappe.get_doc("woocommerce Settings")

	make_woocommerce_log(title="Sync Job Queued", status="Queued", method=frappe.local.form_dict.cmd, message="Sync Job Queued")
	
	if woocommerce_settings.enable_woocommerce:
		try :
			now_time = frappe.utils.now()
			validate_woocommerce_settings(woocommerce_settings)
			frappe.local.form_dict.count_dict = {}
			sync_products(woocommerce_settings.price_list, woocommerce_settings.warehouse)
			sync_customers()
			sync_orders()
			update_item_stock_qty()
			frappe.db.set_value("woocommerce Settings", None, "last_sync_datetime", now_time)
			
			make_woocommerce_log(title="Sync Completed", status="Success", method=frappe.local.form_dict.cmd, 
				message= "Updated {customers} customer(s), {products} item(s), {orders} order(s)".format(**frappe.local.form_dict.count_dict))

		except Exception, e:
			if e.args[0] and hasattr(e.args[0], "startswith") and e.args[0].startswith("402"):
				make_woocommerce_log(title="woocommerce has suspended your account", status="Error",
					method="sync_woocommerce_resources", message=_("""woocommerce has suspended your account till
					you complete the payment. We have disabled ERPNext woocommerce Sync. Please enable it once
					your complete the payment at woocommerce."""), exception=True)

				disable_woocommerce_sync_on_exception()
			
			else:
				make_woocommerce_log(title="sync has terminated", status="Error", method="sync_woocommerce_resources",
					message=frappe.get_traceback(), exception=True)
					
	elif frappe.local.form_dict.cmd == "woocommerceconnector.api.sync_woocommerce":
		make_woocommerce_log(
			title="woocommerce connector is disabled",
			status="Error",
			method="sync_woocommerce_resources",
			message=_("""woocommerce connector is not enabled. Click on 'Connect to woocommerce' to connect ERPNext and your woocommerce store."""),
			exception=True)

def validate_woocommerce_settings(woocommerce_settings):
	"""
		This will validate mandatory fields and access token or app credentials 
		by calling validate() of woocommerce settings.
	"""
	try:
		woocommerce_settings.save()
	except woocommerceError:
		disable_woocommerce_sync_on_exception()

@frappe.whitelist()
def get_log_status():
	log = frappe.db.sql("""select name, status from `tabwoocommerce Log` 
		order by modified desc limit 1""", as_dict=1)
	if log:
		if log[0].status=="Queued":
			message = _("Last sync request is queued")
			alert_class = "alert-warning"
		elif log[0].status=="Error":
			message = _("Last sync request was failed, check <a href='../desk#Form/woocommerce Log/{0}'> here</a>"
				.format(log[0].name))
			alert_class = "alert-danger"
		else:
			message = _("Last sync request was successful")
			alert_class = "alert-success"
			
		return {
			"text": message,
			"alert_class": alert_class
		}
		
