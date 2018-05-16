from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .woocommerce_requests import get_woocommerce_customers, post_request, put_request
from .utils import make_woocommerce_log

def sync_customers():
	woocommerce_customer_list = []
	sync_woocommerce_customers(woocommerce_customer_list)
	frappe.local.form_dict.count_dict["customers"] = len(woocommerce_customer_list)
	
	sync_erpnext_customers(woocommerce_customer_list)

def sync_woocommerce_customers(woocommerce_customer_list):
	for woocommerce_customer in get_woocommerce_customers():
		if not frappe.db.get_value("Customer", {"woocommerce_customer_id": woocommerce_customer.get('id')}, "name"):
			#only synch customers with address
			if woocommerce_customer.get("billing").get("address_1") <> "" and woocommerce_customer.get("shipping").get("address_1")<>"":
				create_customer(woocommerce_customer, woocommerce_customer_list)

def create_customer(woocommerce_customer, woocommerce_customer_list):
	import frappe.utils.nestedset

	make_woocommerce_log(title="create customer", status="Error", method="create_customer",
		message= "create customer",request_data=woocommerce_customer, exception=False)

	woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
	
	cust_name = (woocommerce_customer.get("first_name") + " " + (woocommerce_customer.get("last_name") \
		and  woocommerce_customer.get("last_name") or "")) if woocommerce_customer.get("first_name")\
		else woocommerce_customer.get("email")
		
	try:
		customer = frappe.get_doc({
			"doctype": "Customer",

			"name": woocommerce_customer.get("id"),
			"customer_name" : cust_name,
			"woocommerce_customer_id": woocommerce_customer.get("id"),
			"sync_with_woocommerce": 0,
			"customer_group": woocommerce_settings.customer_group,
			"territory": frappe.utils.nestedset.get_root_of("Territory"),
			"customer_type": _("Individual")
		})
		customer.flags.ignore_mandatory = True
		customer.insert()
		
		if customer:
			create_customer_address(customer, woocommerce_customer)
	
		woocommerce_customer_list.append(woocommerce_customer.get("id"))
		frappe.db.commit()
			
	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_woocommerce_log(title=e.message, status="Error", method="create_customer", message=frappe.get_traceback(),
				request_data=woocommerce_customer, exception=True)
		
def create_customer_address(customer, woocommerce_customer):
	billing_address = woocommerce_customer.get("billing")
	shipping_address = woocommerce_customer.get("shipping")
	
	if billing_address:
                try :
                        frappe.get_doc({
                                "doctype": "Address",
                                "woocommerce_address_id": "Billing",
                                "address_title": customer.name,
                                "address_type": "Billing",
                                "address_line1": billing_address.get("address_1") or "Address 1",
                                "address_line2": billing_address.get("address_2"),
                                "city": billing_address.get("city") or "City",
                                "state": billing_address.get("state"),
                                "pincode": billing_address.get("postcode"),
                                "country": billing_address.get("country"),
                                "phone": billing_address.get("phone"),
                                "email_id": billing_address.get("email"),
                                "links": [{
                                        "link_doctype": "Customer",
                                        "link_name": customer.name
                                }]
                        }).insert()

                except Exception, e:
                        make_woocommerce_log(title=e.message, status="Error", method="create_customer_address", message=frappe.get_traceback(),
                                request_data=woocommerce_customer, exception=True)


		try :
			frappe.get_doc({
				"doctype": "Address",
				"woocommerce_address_id": "Shipping",
				"address_title": customer.name,
				"address_type": "Shipping",
				"address_line1": shipping_address.get("address_1") or "Address 1",
				"address_line2": shipping_address.get("address_2"),
				"city": shipping_address.get("city") or "City",
				"state": shipping_address.get("province"),
				"pincode": shipping_address.get("zip"),
				"country": shipping_address.get("country"),
				"phone": shipping_address.get("phone"),
				"email_id": shipping_address.get("email"),
				"links": [{
					"link_doctype": "Customer",
					"link_name": customer.name
				}]
			}).insert()
			
		except Exception, e:
			make_woocommerce_log(title=e.message, status="Error", method="create_customer_address", message=frappe.get_traceback(),
				request_data=woocommerce_customer, exception=True)
		
#def get_address_title_and_type(customer_name, index):
	#address_type = _("Billing")
	#address_title = customer_name
	#if frappe.db.get_value("Address", "{0}-{1}".format(customer_name.strip(), address_type)):
		#address_title = "{0}-{1}".format(customer_name.strip(), index)
		
	#return address_title, address_type 
	
def sync_erpnext_customers(woocommerce_customer_list):
	woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
	
	condition = ["sync_with_woocommerce = 1"]
	
	last_sync_condition = ""
	if woocommerce_settings.last_sync_datetime:
		last_sync_condition = "modified >= '{0}' ".format(woocommerce_settings.last_sync_datetime)
		condition.append(last_sync_condition)
	
	customer_query = """select name, customer_name, woocommerce_customer_id from tabCustomer 
		where {0}""".format(" and ".join(condition))
		
	for customer in frappe.db.sql(customer_query, as_dict=1):
		try:
			if not customer.woocommerce_customer_id:
				create_customer_to_woocommerce(customer)
			
			else:
				if customer.woocommerce_customer_id not in woocommerce_customer_list:
					update_customer_to_woocommerce(customer, woocommerce_settings.last_sync_datetime)
			
			frappe.local.form_dict.count_dict["customers"] += 1
			frappe.db.commit()
		except Exception, e:
			make_woocommerce_log(title=e.message, status="Error", method="sync_erpnext_customers", message=frappe.get_traceback(),
				request_data=customer, exception=True)

def create_customer_to_woocommerce(customer):
	woocommerce_customer = {
		"first_name": customer['customer_name'],
	}
	
	customer = frappe.get_doc("Customer", customer['name'])
	addresses = get_customer_addresses(customer.as_dict())
	for address in addresses:
		address_type = address.pop("address_type")
		address_name = address.pop("name")
		if address_type == "Shipping":
			woocommerce_customer["shipping"] = address
		if address_type == "Billing":
			woocommerce_customer["billing"] = address		

	make_woocommerce_log(title="what is customer", status="Error", method="create_customer_to_woocommerce",
		message= "what is cusotmer",request_data=woocommerce_customer, exception=False)
	woocommerce_customer = post_request("customers", woocommerce_customer)
	customer.woocommerce_customer_id = woocommerce_customer.get("id")
	
	customer.flags.ignore_mandatory = True
	customer.save()
	

def sync_customer_address(customer, address):
	address_name = address.pop("name")

	woocommerce_address = post_request("/admin/customers/{0}/addresses.json".format(customer.woocommerce_customer_id),
	{"address": address})
		
	address = frappe.get_doc("Address", address_name)
	address.woocommerce_address_id = woocommerce_address['customer_address'].get("id")
	address.save()
	
def update_customer_to_woocommerce(customer, last_sync_datetime):
	woocommerce_customer = {
		"first_name": customer['customer_name'],
		"last_name": ""
	}
	
	try:
		put_request("/admin/customers/{0}.json".format(customer.woocommerce_customer_id),\
			{ "customer": woocommerce_customer})
		update_address_details(customer, last_sync_datetime)
		
	except requests.exceptions.HTTPError, e:
		if e.args[0] and e.args[0].startswith("404"):
			customer = frappe.get_doc("Customer", customer.name)
			customer.woocommerce_customer_id = ""
			customer.sync_with_woocommerce = 0
			customer.flags.ignore_mandatory = True
			customer.save()
		else:
			raise
			
def update_address_details(customer, last_sync_datetime):
	customer_addresses = get_customer_addresses(customer, last_sync_datetime)
	for address in customer_addresses:
		if address.woocommerce_address_id:
			url = "/admin/customers/{0}/addresses/{1}.json".format(customer.woocommerce_customer_id,\
			address.woocommerce_address_id)
			
			address["id"] = address["woocommerce_address_id"]
			
			del address["woocommerce_address_id"]
			
			put_request(url, { "address": address})
			
		else:
			sync_customer_address(customer, address)
			
def get_customer_addresses(customer, last_sync_datetime=None):
	conditions = ["dl.parent = addr.name", "dl.link_doctype = 'Customer'",
		"dl.link_name = '{0}'".format(customer['name'])]
	
	if last_sync_datetime:
		last_sync_condition = "addr.modified >= '{0}'".format(last_sync_datetime)
		conditions.append(last_sync_condition)
	
	address_query = """select addr.name, addr.address_line1 as address1, addr.address_line2 as address2,
		addr.city as city, addr.state as province, addr.country as country, addr.pincode as zip,
		addr.woocommerce_address_id from tabAddress addr, `tabDynamic Link` dl
		where {0}""".format(' and '.join(conditions))
			
	return frappe.db.sql(address_query, as_dict=1)
