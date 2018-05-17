from __future__ import unicode_literals
import frappe
from frappe import _
from .exceptions import woocommerceError
from .utils import make_woocommerce_log
from .sync_products import make_item
from .sync_customers import create_customer
from frappe.utils import flt, nowdate, cint
from .woocommerce_requests import get_request, get_woocommerce_orders, get_woocommerce_tax, get_woocommerce_customer, put_request
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice


def sync_orders():
	sync_woocommerce_orders()

def sync_woocommerce_orders():
	frappe.local.form_dict.count_dict["orders"] = 0
	woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
	
	for woocommerce_order in get_woocommerce_orders():
		if valid_customer_and_product(woocommerce_order):
			try:
				create_order(woocommerce_order, woocommerce_settings)
				frappe.local.form_dict.count_dict["orders"] += 1

			except woocommerceError, e:
				make_woocommerce_log(status="Error", method="sync_woocommerce_orders", message=frappe.get_traceback(),
					request_data=woocommerce_order, exception=True)
			except Exception, e:
				if e.args and e.args[0] and e.args[0].decode("utf-8").startswith("402"):
					raise e
				else:
					make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_orders", message=frappe.get_traceback(),
						request_data=woocommerce_order, exception=True)
				
def valid_customer_and_product(woocommerce_order):
	customer_id = woocommerce_order.get("customer_id")
	if customer_id == 0: # we are dealing with a guest customer 
		woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
		if not woocommerce_settings.default_customer:
			make_woocommerce_log(title="Missing Default Customer", status="Error", method="valid_customer_and_product", message="Missing Default Customer in Woocommerce Settings",
				request_data=woocommerce_order, exception=True)
			return False
	
	if customer_id > 0:
		if not frappe.db.get_value("Customer", {"woocommerce_customer_id": customer_id}, "name", False,True):
			woocommerce_customer = get_woocommerce_customer(customer_id)

			#Customer may not have billing and shipping address on file, pull it from the order
			if woocommerce_customer["billing"].get("address_1") == "":
				woocommerce_customer["billing"] = woocommerce_order["billing"]
				woocommerce_customer["billing"]["country"] = get_country_from_code( woocommerce_customer.get("billing").get("country") )

                        if woocommerce_customer["shipping"].get("address_1") == "":
                                woocommerce_customer["shipping"] = woocommerce_order["shipping"]
                                woocommerce_customer["shipping"]["country"] = get_country_from_code( woocommerce_customer.get("shipping").get("country") )
			
			create_customer(woocommerce_customer, woocommerce_customer_list=[])	  

	warehouse = frappe.get_doc("woocommerce Settings", "woocommerce Settings").warehouse
	for item in woocommerce_order.get("line_items"):
		if item.get("product_id") and not frappe.db.get_value("Item", {"woocommerce_product_id": item.get("product_id")}, "name"):
			item = get_request("products/{0}".format(item.get("product_id")))["product"]
			make_item(warehouse, item, woocommerce_item_list=[])

	return True

def get_country_from_code(country_code):
	return frappe.db.get_value("Country", {"code": country_code}, "name")





def create_order(woocommerce_order, woocommerce_settings, company=None):
	so = create_sales_order(woocommerce_order, woocommerce_settings, company)
	if woocommerce_order.get("status") == "completed" and cint(woocommerce_settings.sync_sales_invoice):
		create_sales_invoice(woocommerce_order, woocommerce_settings, so)

	#Fix this -- add shipping stuff
	#if woocommerce_order.get("fulfillments") and cint(woocommerce_settings.sync_delivery_note):
		#create_delivery_note(woocommerce_order, woocommerce_settings, so)

def create_sales_order(woocommerce_order, woocommerce_settings, company=None):
	customer = frappe.db.get_value("Customer", {"woocommerce_customer_id": woocommerce_order.get("customer_id")}, "name")
		
	so = frappe.db.get_value("Sales Order", {"woocommerce_order_id": woocommerce_order.get("id")}, "name")
	if not so:
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"naming_series": woocommerce_settings.sales_order_series or "SO-woocommerce-",
			"woocommerce_order_id": woocommerce_order.get("id"),
			"customer": customer or woocommerce_settings.default_customer,
			"delivery_date": nowdate(),
			"company": woocommerce_settings.company,
			"selling_price_list": woocommerce_settings.price_list,
			"ignore_pricing_rule": 1,
			"items": get_order_items(woocommerce_order.get("line_items"), woocommerce_settings),
			"taxes": get_order_taxes(woocommerce_order, woocommerce_settings),
			"apply_discount_on": "Grand Total",
			"discount_amount": flt(woocommerce_order.get("discount_total") or 0),
		})

		so.flags.ignore_mandatory = True

		if woocommerce_order.get("status") == "on-hold":
			so.save(ignore_permissions=True)
		elif woocommerce_order.get("status") in ("cancelled", "refunded", "failed"):
			so.save(ignore_permissions=True)
			so.submit()
			so.cancel()
		else:
			so.save(ignore_permissions=True)
			so.submit()

	else:
		so = frappe.get_doc("Sales Order", so)

	frappe.db.commit()
	return so

def create_sales_invoice(woocommerce_order, woocommerce_settings, so):
	if not frappe.db.get_value("Sales Invoice", {"woocommerce_order_id": woocommerce_order.get("id")}, "name")\
		and so.docstatus==1 and not so.per_billed:
		si = make_sales_invoice(so.name)
		si.woocommerce_order_id = woocommerce_order.get("id")
		si.naming_series = woocommerce_settings.sales_invoice_series or "SI-woocommerce-"
		si.flags.ignore_mandatory = True
		set_cost_center(si.items, woocommerce_settings.cost_center)
		si.submit()
		make_payament_entry_against_sales_invoice(si, woocommerce_settings)
		frappe.db.commit()

def set_cost_center(items, cost_center):
	for item in items:
		item.cost_center = cost_center

def make_payament_entry_against_sales_invoice(doc, woocommerce_settings):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	payemnt_entry = get_payment_entry(doc.doctype, doc.name, bank_account=woocommerce_settings.cash_bank_account)
	payemnt_entry.flags.ignore_mandatory = True
	payemnt_entry.reference_no = doc.name
	payemnt_entry.reference_date = nowdate()
	payemnt_entry.submit()

def create_delivery_note(woocommerce_order, woocommerce_settings, so):
	for fulfillment in woocommerce_order.get("fulfillments"):
		if not frappe.db.get_value("Delivery Note", {"woocommerce_fulfillment_id": fulfillment.get("id")}, "name")\
			and so.docstatus==1:
			dn = make_delivery_note(so.name)
			dn.woocommerce_order_id = fulfillment.get("order_id")
			dn.woocommerce_fulfillment_id = fulfillment.get("id")
			dn.naming_series = woocommerce_settings.delivery_note_series or "DN-woocommerce-"
			dn.items = get_fulfillment_items(dn.items, fulfillment.get("line_items"), woocommerce_settings)
			dn.flags.ignore_mandatory = True
			dn.save()
			frappe.db.commit()

def get_fulfillment_items(dn_items, fulfillment_items, woocommerce_settings):

	return [dn_item.update({"qty": item.get("quantity")}) for item in fulfillment_items for dn_item in dn_items\
			if get_item_code(item) == dn_item.item_code]
	
#def get_discounted_amount(order):
	#discounted_amount = flt(order.get("discount_total") or 0)
	#return discounted_amount

def get_order_items(order_items, woocommerce_settings):
	items = []
	for woocommerce_item in order_items:
		item_code = get_item_code(woocommerce_item)
		items.append({
			"item_code": item_code,
			"item_name": woocommerce_item.get("name"),
			"rate": woocommerce_item.get("price"),
			"delivery_date": nowdate(),
			"qty": woocommerce_item.get("quantity"),
			"stock_uom": woocommerce_item.get("sku"),
			"warehouse": woocommerce_settings.warehouse
		})
	return items

def get_item_code(woocommerce_item):
	item_code = frappe.db.get_value("Item", {"woocommerce_variant_id": woocommerce_item.get("variation_id")}, "item_code")
	if not item_code:
		item_code = frappe.db.get_value("Item", {"woocommerce_product_id": woocommerce_item.get("product_id")}, "item_code")
	#if not item_code:
		#item_code = frappe.db.get_value("Item", {"item_name": woocommerce_item.get("title")}, "item_code")

	return item_code

def get_order_taxes(woocommerce_order, woocommerce_settings):
	taxes = []
	for tax in woocommerce_order.get("tax_lines"):
		
		woocommerce_tax = get_woocommerce_tax(tax.get("rate_id"))
		rate = woocommerce_tax.get("rate")
		name = woocommerce_tax.get("name")
		
		taxes.append({
			"charge_type": _("Actual"),
			"account_head": get_tax_account_head(woocommerce_tax),
			"description": "{0} - {1}%".format(name, rate),
			#"rate": rate,
			"tax_amount": flt(tax.get("tax_total") or 0) + flt(tax.get("shipping_tax_total") or 0), 
			"included_in_print_rate": 1 if woocommerce_order.get("prices_include_tax") else 0,
			"cost_center": woocommerce_settings.cost_center
		})
	taxes = update_taxes_with_fee_lines(taxes, woocommerce_order.get("fee_lines"), woocommerce_settings)
	taxes = update_taxes_with_shipping_lines(taxes, woocommerce_order.get("shipping_lines"), woocommerce_settings)

	return taxes

def update_taxes_with_fee_lines(taxes, fee_lines, woocommerce_settings):
	for fee_charge in fee_lines:
		taxes.append({
			"charge_type": _("Actual"),
			"account_head": woocommerce_settings.fee_account,
			"description": fee_charge["name"],
			"tax_amount": fee_charge["amount"],
			"cost_center": woocommerce_settings.cost_center
		})

	return taxes

def update_taxes_with_shipping_lines(taxes, shipping_lines, woocommerce_settings):
	for shipping_charge in shipping_lines:
		#
		taxes.append({
			"charge_type": _("Actual"),
			"account_head": get_shipping_account_head(shipping_charge),
			"description": shipping_charge["method_title"],
			"tax_amount": shipping_charge["total"],
			"cost_center": woocommerce_settings.cost_center
		})

	return taxes



def get_shipping_account_head(shipping):
        shipping_title = shipping.get("method_title").encode("utf-8")

        shipping_account =  frappe.db.get_value("woocommerce Tax Account", \
                {"parent": "woocommerce Settings", "woocommerce_tax": shipping_title}, "tax_account")

        if not shipping_account:
                frappe.throw("Tax Account not specified for woocommerce shipping method  {0}".format(shipping.get("method_title")))

        return shipping_account


def get_tax_account_head(tax):
	tax_title = tax.get("name").encode("utf-8") or tax.get("method_title").encode("utf-8")

	tax_account =  frappe.db.get_value("woocommerce Tax Account", \
		{"parent": "woocommerce Settings", "woocommerce_tax": tax_title}, "tax_account")

	if not tax_account:
		frappe.throw("Tax Account not specified for woocommerce Tax {0}".format(tax.get("name")))

	return tax_account

def close_synced_woocommerce_orders():
	for woocommerce_order in get_woocommerce_orders():
		order_data = {
			"status": "completed"
		}
		try:
			put_request("orders/{0}".format(woocommerce_order.get("id")), order_data)
				
		except requests.exceptions.HTTPError, e:
			make_woocommerce_log(title=e.message, status="Error", method="close_synced_woocommerce_orders", message=frappe.get_traceback(),
				request_data=woocommerce_order, exception=True)