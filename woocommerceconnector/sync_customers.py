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

def sync_woocommerce_customers(woocommerce_customer_list):
    for woocommerce_customer in get_woocommerce_customers():
        # import new customer or update existing customer
        if not frappe.db.get_value("Customer", {"woocommerce_customer_id": woocommerce_customer.get('id')}, "name"):
            #only synch customers with address
            if woocommerce_customer.get("billing").get("address_1") != "" and woocommerce_customer.get("shipping").get("address_1") != "":
                create_customer(woocommerce_customer, woocommerce_customer_list)
        else:
            update_customer(woocommerce_customer)

def update_customer(woocommerce_customer):
    return

def create_customer(woocommerce_customer, woocommerce_customer_list):
    import frappe.utils.nestedset

    woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
    
    cust_name = (woocommerce_customer.get("first_name") + " " + (woocommerce_customer.get("last_name") \
        and  woocommerce_customer.get("last_name") or "")) if woocommerce_customer.get("first_name")\
        else woocommerce_customer.get("email")
        
    try:
        # try to match territory
        country_code = get_country_name(woocommerce_customer["billing"]["country"])
        country_matches = frappe.get_all("Country", filters={'code': country_code}, fields=['name'])
        if country_matches:
            if frappe.db.exists("Territory", country_matches[0]['name']):
                territory = country_matches[0]['name']
            else:
                territory = frappe.utils.nestedset.get_root_of("Territory")
        else:
            territory = frappe.utils.nestedset.get_root_of("Territory")
        customer = frappe.get_doc({
            "doctype": "Customer",
            "name": woocommerce_customer.get("id"),
            "customer_name" : cust_name,
            "woocommerce_customer_id": woocommerce_customer.get("id"),
            "sync_with_woocommerce": 0,
            "customer_group": woocommerce_settings.customer_group,
            "territory": territory,
            "customer_type": _("Individual")
        })
        customer.flags.ignore_mandatory = True
        customer.insert()
        
        if customer:
            create_customer_address(customer, woocommerce_customer)
            create_customer_contact(customer, woocommerce_customer)
    
        woocommerce_customer_list.append(woocommerce_customer.get("id"))
        frappe.db.commit()
        make_woocommerce_log(title="create customer", status="Success", method="create_customer",
            message= "create customer",request_data=woocommerce_customer, exception=False)
            
    except Exception as e:
        if e.args[0] and e.args[0].startswith("402"):
            raise e
        else:
            make_woocommerce_log(title=e.message, status="Error", method="create_customer", message=frappe.get_traceback(),
                request_data=woocommerce_customer, exception=True)
        
def create_customer_address(customer, woocommerce_customer):
    billing_address = woocommerce_customer.get("billing")
    shipping_address = woocommerce_customer.get("shipping")
    
    if billing_address:
        country = get_country_name(billing_address.get("country"))
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
                "country": country,
                "phone": billing_address.get("phone"),
                "email_id": billing_address.get("email"),
                "links": [{
                    "link_doctype": "Customer",
                    "link_name": customer.name
                }]
            }).insert()

        except Exception as e:
            make_woocommerce_log(title=e.message, status="Error", method="create_customer_address", message=frappe.get_traceback(),
                    request_data=woocommerce_customer, exception=True)

    if shipping_address:
        country = get_country_name(shipping_address.get("country"))
        try :
            frappe.get_doc({
                "doctype": "Address",
                "woocommerce_address_id": "Shipping",
                "address_title": customer.name,
                "address_type": "Shipping",
                "address_line1": shipping_address.get("address_1") or "Address 1",
                "address_line2": shipping_address.get("address_2"),
                "city": shipping_address.get("city") or "City",
                "state": shipping_address.get("state"),
                "pincode": shipping_address.get("postcode"),
                "country": country,
                "phone": shipping_address.get("phone"),
                "email_id": shipping_address.get("email"),
                "links": [{
                    "link_doctype": "Customer",
                    "link_name": customer.name
                }]
            }).insert()
            
        except Exception as e:
            make_woocommerce_log(title=e.message, status="Error", method="create_customer_address", message=frappe.get_traceback(),
                request_data=woocommerce_customer, exception=True)

def create_customer_contact(customer, woocommerce_customer):
    try :
        frappe.get_doc({
            "doctype": "Contact",
            "first_name": woocommerce_customer["billing"]["first_name"],
            "last_name": woocommerce_customer["billing"]["last_name"],
            "email_id": woocommerce_customer["billing"]["email"],
            "phone": woocommerce_customer["billing"]["phone"],
            "links": [{
                "link_doctype": "Customer",
                "link_name": customer.name
            }]
        }).insert()

    except Exception as e:
        make_woocommerce_log(title=e.message, status="Error", method="create_customer_contact", message=frappe.get_traceback(),
                request_data=woocommerce_customer, exception=True)

def get_country_name(code):
    coutry_name = ''
    coutry_names = """SELECT `country_name` FROM `tabCountry` WHERE `code` = '{0}'""".format(code.lower())
    for _coutry_name in frappe.db.sql(coutry_names, as_dict=1):
        coutry_name = _coutry_name.country_name
    return coutry_name
