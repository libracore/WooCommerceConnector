from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .exceptions import woocommerceError
from .utils import make_woocommerce_log, disable_woocommerce_sync_for_item
from erpnext.stock.utils import get_bin
from frappe.utils import cstr, flt, cint, get_files_path
from .woocommerce_requests import post_request, get_woocommerce_items,get_woocommerce_item_variants,  put_request, get_woocommerce_item_image
import base64, requests, datetime, os

woocommerce_variants_attr_list = ["option1", "option2", "option3"]

def sync_products(price_list, warehouse):
    woocommerce_item_list = []
    sync_woocommerce_items(warehouse, woocommerce_item_list)
    frappe.local.form_dict.count_dict["products"] = len(woocommerce_item_list)
    sync_erpnext_items(price_list, warehouse, woocommerce_item_list)

def sync_woocommerce_items(warehouse, woocommerce_item_list):
    for woocommerce_item in get_woocommerce_items():
        try:
            make_item(warehouse, woocommerce_item, woocommerce_item_list)

        except woocommerceError as e:
            make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
                request_data=woocommerce_item, exception=True)

        except Exception as e:
            if e.args[0] and e.args[0].startswith("402"):
                raise e
            else:
                make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
                    request_data=woocommerce_item, exception=True)

def make_item(warehouse, woocommerce_item, woocommerce_item_list):

    if has_variants(woocommerce_item):
        #replace woocommerce variants id array with actual variant info
        woocommerce_item['variants'] = get_woocommerce_item_variants(woocommerce_item.get("id"))
        
        attributes = create_attribute(woocommerce_item)
        create_item(woocommerce_item, warehouse, 1, attributes, woocommerce_item_list=woocommerce_item_list)
        create_item_variants(woocommerce_item, warehouse, attributes, woocommerce_variants_attr_list, woocommerce_item_list=woocommerce_item_list)

    else:
        """woocommerce_item["variant_id"] = woocommerce_item['variants'][0]["id"]"""
        create_item(woocommerce_item, warehouse, woocommerce_item_list=woocommerce_item_list)

def has_variants(woocommerce_item):
    if len(woocommerce_item.get("variations")) >= 1:
        return True
    return False

def create_attribute(woocommerce_item):
    attribute = []
    # woocommerce item dict
    for attr in woocommerce_item.get('attributes'):
        if not frappe.db.get_value("Item Attribute", attr.get("name"), "name"):
            frappe.get_doc({
                "doctype": "Item Attribute",
                "attribute_name": attr.get("name"),
                "woocommerce_attribute_id": attr.get("id"),
                "item_attribute_values": [
                    {
                        "attribute_value": attr_value,
                        "abbr":attr_value
                    }
                    for attr_value in attr.get("options")
                ]
            }).insert()
            attribute.append({"attribute": attr.get("name")})
        else:
            # check for attribute values
            item_attr = frappe.get_doc("Item Attribute", attr.get("name"))
            if not item_attr.numeric_values:
                if not item_attr.get("woocommerce_attribute_id"):
                                item_attr.woocommerce_attribute_id = attr.get("id")
                set_new_attribute_values(item_attr,  attr.get("options"))
                item_attr.save()
                attribute.append({"attribute": attr.get("name")})

            #else:
                #attribute.append({
                    #"attribute": attr.get("name"),
                    #"from_range": item_attr.get("from_range"),
                    #"to_range": item_attr.get("to_range"),
                    #"increment": item_attr.get("increment"),
                    #"numeric_values": item_attr.get("numeric_values")
                #})

    return attribute

def set_new_attribute_values(item_attr, values):
    for attr_value in values:
        if not any((d.abbr.lower() == attr_value.lower() or d.attribute_value.lower() == attr_value.lower())\
        for d in item_attr.item_attribute_values):
            item_attr.append("item_attribute_values", {
                "attribute_value": attr_value,
                "abbr": attr_value
            })

def create_item(woocommerce_item, warehouse, has_variant=0, attributes=None,variant_of=None, woocommerce_item_list=[]):
    woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
    valuation_method = woocommerce_settings.get("valuation_method")
    weight_unit =  woocommerce_settings.get("weight_unit")
    

    item_dict = {
        "doctype": "Item",
        "woocommerce_product_id": woocommerce_item.get("id"),
        "woocommerce_variant_id": woocommerce_item.get("id"),
        "variant_of": variant_of,
        "sync_with_woocommerce": 1,
        "is_stock_item": 1,
        "item_code": str(woocommerce_item.get("id")) + " " + woocommerce_item.get("name"),
        "item_name": woocommerce_item.get("name"),
        "valuation_method": valuation_method,
        "description": woocommerce_item.get("description") or woocommerce_item.get("name"),
        "woocommerce_description": woocommerce_item.get("description") or woocommerce_item.get("name"),
        "woocommerce_short_description": woocommerce_item.get("short_description") or woocommerce_item.get("name"),
        # "item_group": get_item_group(woocommerce_item.get("categories")), # deactivated according to #1127
        "has_variants": has_variant,
        "attributes": attributes or [],
        "stock_uom": woocommerce_item.get("uom") or _("Nos"),
        "stock_keeping_unit": woocommerce_item.get("sku"), #or get_sku(woocommerce_item),
        "default_warehouse": warehouse,
        "image": get_item_image(woocommerce_item),
        "weight_uom":  weight_unit, #woocommerce_item.get("weight_unit"),
        "weight_per_unit": woocommerce_item.get("weight")
    }
    item_dict["web_long_description"] = item_dict["woocommerce_description"]

    if not is_item_exists(item_dict, attributes, variant_of=variant_of, woocommerce_item_list=woocommerce_item_list):
        item_details = get_item_details(woocommerce_item)

        if not item_details:
            new_item = frappe.get_doc(item_dict)
            new_item.insert()
            name = new_item.name

        else:
            update_item(item_details, item_dict)
            name = item_details.name

        if not has_variant:
            add_to_price_list(woocommerce_item, name)

        frappe.db.commit()

def create_item_variants(woocommerce_item, warehouse, attributes, woocommerce_variants_attr_list, woocommerce_item_list):
    template_item = frappe.db.get_value("Item", filters={"woocommerce_product_id": woocommerce_item.get("id")},
        fieldname=["name", "stock_uom"], as_dict=True)
    

    if template_item:
        for variant in woocommerce_item.get("variants"):
            woocommerce_item_variant = {
                "id" : variant.get("id"),
                "woocommerce_variant_id" : variant.get("id"),
                "name": woocommerce_item.get("name"),
                "item_code":  str(variant.get("id")) + " " + woocommerce_item.get("name"),
                "title": variant.get("name"),
                # "item_group": get_item_group(woocommerce_item.get("")),  # deactivated, no category update
                "sku": variant.get("sku"),
                "uom": template_item.stock_uom or _("Nos"),
                "item_price": variant.get("price"),
                "variant_id": variant.get("id"),
                "weight_unit": variant.get("weight_unit"),
                "net_weight": variant.get("weight")
            }

            woocommerce_variants_attr_list = variant.get("attributes")
            for i, variant_attr in enumerate(woocommerce_variants_attr_list):
                woocommerce_item_variant["name"] = woocommerce_item_variant["name"] + "-" + str(variant_attr.get("option"))
                attributes[i].update({"attribute_value": get_attribute_value(variant_attr.get("option"), variant_attr)})
            
            create_item(woocommerce_item_variant, warehouse, 0, attributes, template_item.name, woocommerce_item_list=woocommerce_item_list)





def get_attribute_value(variant_attr_val, attribute):
    attribute_value = frappe.db.sql("""select attribute_value from `tabItem Attribute Value`
        where parent = %s and (abbr = %s or attribute_value = %s)""", (attribute["name"], variant_attr_val,
        variant_attr_val), as_list=1)
    return attribute_value[0][0] if len(attribute_value)>0 else cint(variant_attr_val)

def get_item_group(product_type=None):
    
    #woocommerce supports multiple categories per item, so we just pick a default in ERPNext
    woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
    return woocommerce_settings.get("default_item_group")

def add_to_price_list(item, name):
    price_list = frappe.db.get_value("woocommerce Settings", None, "price_list")
    item_price_name = frappe.db.get_value("Item Price",
        {"item_code": name, "price_list": price_list}, "name")

    if not item_price_name:
        frappe.get_doc({
            "doctype": "Item Price",
            "price_list": price_list,
            "item_code": name,
            "price_list_rate": item.get("price") or item.get("item_price")   
        }).insert()
    else:
        item_rate = frappe.get_doc("Item Price", item_price_name)
        item_rate.price_list_rate = item.get("price")  or item.get("item_price") 
        item_rate.save()

def get_item_image(woocommerce_item):
    if woocommerce_item.get("images"):
        for image in woocommerce_item.get("images"):
            if image.get("position") == 0: # the featured image
                return image.get("src")
            return None
    else:
        return None

def get_item_details(woocommerce_item):
    item_details = {}

    item_details = frappe.db.get_value("Item", {"woocommerce_product_id": woocommerce_item.get("id")},
        ["name", "stock_uom", "item_name"], as_dict=1)

    if item_details:
        return item_details

    else:
        item_details = frappe.db.get_value("Item", {"woocommerce_variant_id": woocommerce_item.get("id")},
            ["name", "stock_uom", "item_name"], as_dict=1)
        return item_details

#fix this
def is_item_exists(woocommerce_item, attributes=None, variant_of=None, woocommerce_item_list=[]):
    if variant_of:
        name = variant_of
    else:
        name = frappe.db.get_value("Item", {"item_name": woocommerce_item.get("item_name")})

    woocommerce_item_list.append(cstr(woocommerce_item.get("woocommerce_product_id")))

    if name:
        item = frappe.get_doc("Item", name)
        item.flags.ignore_mandatory=True

        if not variant_of and not item.woocommerce_product_id:
            item.woocommerce_product_id = woocommerce_item.get("woocommerce_product_id")
            item.woocommerce_variant_id = woocommerce_item.get("woocommerce_variant_id")
            item.save()
            return False

        if item.woocommerce_product_id and attributes and attributes[0].get("attribute_value"):
            if not variant_of:
                variant_of = frappe.db.get_value("Item",
                    {"woocommerce_product_id": item.woocommerce_product_id}, "variant_of")

            # create conditions for all item attributes,
            # as we are putting condition basis on OR it will fetch all items matching either of conditions
            # thus comparing matching conditions with len(attributes)
            # which will give exact matching variant item.

            conditions = ["(iv.attribute='{0}' and iv.attribute_value = '{1}')"\
                .format(attr.get("attribute"), attr.get("attribute_value")) for attr in attributes]

            conditions = "( {0} ) and iv.parent = it.name ) = {1}".format(" or ".join(conditions), len(attributes))

            parent = frappe.db.sql(""" select * from tabItem it where
                ( select count(*) from `tabItem Variant Attribute` iv
                    where {conditions} and it.variant_of = %s """.format(conditions=conditions) ,
                variant_of, as_list=1)

            if parent:
                variant = frappe.get_doc("Item", parent[0][0])
                variant.flags.ignore_mandatory = True

                variant.woocommerce_product_id = woocommerce_item.get("woocommerce_product_id")
                variant.woocommerce_variant_id = woocommerce_item.get("woocommerce_variant_id")
                variant.save()
            return False

        if item.woocommerce_product_id and item.woocommerce_product_id != woocommerce_item.get("woocommerce_product_id"):
            return False

        return True

    else:
        return False

def update_item(item_details, item_dict):
    item = frappe.get_doc("Item", item_details.name)
        
    item_dict["stock_uom"] = item_details.stock_uom

    if not item_dict["web_long_description"]:
        del item_dict["web_long_description"]

    if item_dict.get("warehouse"):
        del item_dict["warehouse"]

    del item_dict["description"]
    del item_dict["item_code"]
    del item_dict["variant_of"]
    del item_dict["item_name"]

    item.update(item_dict)
    item.flags.ignore_mandatory = True
    item.save()

def sync_erpnext_items(price_list, warehouse, woocommerce_item_list):
    for item in get_erpnext_items(price_list):
        if item.woocommerce_product_id not in woocommerce_item_list:
            try:
                sync_item_with_woocommerce(item, price_list, warehouse)
                frappe.local.form_dict.count_dict["products"] += 1

            except woocommerceError as e:
                make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
                    request_data=item, exception=True)
            except Exception as e:
                make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
                    request_data=item, exception=True)

def get_erpnext_items(price_list):
    erpnext_items = []
    woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")

    last_sync_condition, item_price_condition = "", ""
    if woocommerce_settings.last_sync_datetime:
        last_sync_condition = "and modified >= '{0}' ".format(woocommerce_settings.last_sync_datetime)
        item_price_condition = "and ip.modified >= '{0}' ".format(woocommerce_settings.last_sync_datetime)

    item_from_master = """select name, item_code, item_name, item_group,
        description, woocommerce_description, has_variants, variant_of, stock_uom, image, woocommerce_product_id, 
        woocommerce_variant_id, sync_qty_with_woocommerce, weight_per_unit, weight_uom, default_supplier from tabItem
        where sync_with_woocommerce=1 and (variant_of is null or variant_of = '')
        and (disabled is null or disabled = 0)  %s """ % last_sync_condition

    erpnext_items.extend(frappe.db.sql(item_from_master, as_dict=1))

    template_items = [item.name for item in erpnext_items if item.has_variants]

    if len(template_items) > 0:
        item_price_condition += ' and i.variant_of not in (%s)'%(' ,'.join(["'%s'"]*len(template_items)))%tuple(template_items)

    item_from_item_price = """select i.name, i.item_code, i.item_name, i.item_group, i.description,
        i.woocommerce_description, i.has_variants, i.variant_of, i.stock_uom, i.image, i.woocommerce_product_id,
        i.woocommerce_variant_id, i.sync_qty_with_woocommerce, i.weight_per_unit, i.weight_uom,
        i.default_supplier from `tabItem` i, `tabItem Price` ip
        where price_list = '%s' and i.name = ip.item_code
            and sync_with_woocommerce=1 and (disabled is null or disabled = 0) %s""" %(price_list, item_price_condition)

    updated_price_item_list = frappe.db.sql(item_from_item_price, as_dict=1)

    # to avoid item duplication
    return [frappe._dict(tupleized) for tupleized in set(tuple(item.items())
        for item in erpnext_items + updated_price_item_list)]

def sync_item_with_woocommerce(item, price_list, warehouse):
    variant_item_name_list = []
    variant_list = []
    item_data = {
            "name": item.get("item_name"),
            "description": item.get("woocommerce_description") or item.get("web_long_description") or item.get("description"),
            "short_description": item.get("woocommerce_description") or item.get("web_long_description") or item.get("description"),
            "categories" : [],
            "images": []
    }
    item_data.update( get_price_and_stock_details(item, warehouse, price_list) )

    if item.get("has_variants"):  # we are dealing a variable product
        item_data["type"] = "variable"
        
        if item.get("variant_of"):
            item = frappe.get_doc("Item", item.get("variant_of"))

        variant_list, options, variant_item_name = get_variant_attributes(item, price_list, warehouse)
        item_data["attributes"] = options

    else:   # we are dealing with a simple product
        item_data["type"] = "simple"  
            

    erp_item = frappe.get_doc("Item", item.get("name"))
    erp_item.flags.ignore_mandatory = True
    
    if not item.get("woocommerce_product_id"):
        item_data["status"] = "draft"
        
        create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list)

    else:
        item_data["id"] = item.get("woocommerce_product_id")
        try:
            put_request("products/{0}".format(item.get("woocommerce_product_id")), item_data)
            
        except requests.exceptions.HTTPError, e:
            if e.args[0] and e.args[0].startswith("404"):
                if frappe.db.get_value("woocommerce Settings", "woocommerce Settings", "if_not_exists_create_item_to_woocommerce"):
                    item_data["id"] = ''
                    create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list)
                else:
                    disable_woocommerce_sync_for_item(erp_item)
            else:
                raise e
        
    if variant_list:  
        for variant in variant_list:
            erp_varient_item = frappe.get_doc("Item", variant["item_name"])
            if erp_varient_item.woocommerce_product_id: #varient exist in woocommerce let's update only  
                r = put_request("products/{0}/variations/{1}".format(erp_item.woocommerce_product_id, erp_varient_item.woocommerce_product_id),variant)
            else:    
                woocommerce_variant = post_request("products/{0}/variations".format(erp_item.woocommerce_product_id), variant) 
                
                erp_varient_item.woocommerce_product_id = woocommerce_variant.get("id")
                erp_varient_item.woocommerce_variant_id = woocommerce_variant.get("id")
                erp_varient_item.save()
                
    # rlavaud let's not sych image willy nilly
    #sync_item_image(erp_item)  
    frappe.db.commit()


def create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list):
    new_item = post_request("products", item_data)
    
    erp_item.woocommerce_product_id = new_item.get("id")

    #if not item.get("has_variants"):
        #erp_item.woocommerce_variant_id = new_item['product']["variants"][0].get("id")

    erp_item.save()
    #update_variant_item(new_item, variant_item_name_list)

def sync_item_image(item):
    image_info = {
        "image": {}
    }

    if item.image:
        img_details = frappe.db.get_value("File", {"file_url": item.image}, ["file_name", "content_hash"])

        if img_details and img_details[0] and img_details[1]:
            is_private = item.image.startswith("/private/files/")

            with open(get_files_path(img_details[0].strip("/"), is_private=is_private), "rb") as image_file:
                image_info["image"]["attachment"] = base64.b64encode(image_file.read())
            image_info["image"]["filename"] = img_details[0]

            #to avoid 422 : Unprocessable Entity
            if not image_info["image"]["attachment"] or not image_info["image"]["filename"]:
                return False

        elif item.image.startswith("http") or item.image.startswith("ftp"):
            if validate_image_url(item.image):
                #to avoid 422 : Unprocessable Entity
                image_info["image"]["src"] = item.image

        if image_info["image"]:
            if not item_image_exists(item.woocommerce_product_id, image_info):
                # to avoid image duplication
                post_request("/admin/products/{0}/images.json".format(item.woocommerce_product_id), image_info)


def validate_image_url(url):
    """ check on given url image exists or not"""
    res = requests.get(url)
    if res.headers.get("content-type") in ('image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/tiff'):
        return True
    return False

def item_image_exists(woocommerce_product_id, image_info):
    """check same image exist or not"""
    for image in get_woocommerce_item_image(woocommerce_product_id):
        if image_info.get("image").get("filename"):
            if os.path.splitext(image.get("src"))[0].split("/")[-1] == os.path.splitext(image_info.get("image").get("filename"))[0]:
                return True
        elif image_info.get("image").get("src"):
            if os.path.splitext(image.get("src"))[0].split("/")[-1] == os.path.splitext(image_info.get("image").get("src"))[0].split("/")[-1]:
                return True
        else:
            return False

def update_variant_item(new_item, item_code_list):
    for i, name in enumerate(item_code_list):
        erp_item = frappe.get_doc("Item", name)
        erp_item.flags.ignore_mandatory = True
        erp_item.woocommerce_product_id = new_item['product']["variants"][i].get("id")
        erp_item.woocommerce_variant_id = new_item['product']["variants"][i].get("id")
        erp_item.save()

def get_variant_attributes(item, price_list, warehouse):
    options, variant_list, variant_item_name, attr_sequence = [], [], [], []
    attr_dict = {}

    for i, variant in enumerate(frappe.get_all("Item", filters={"variant_of": item.get("name")},
        fields=['name'])):

        item_variant = frappe.get_doc("Item", variant.get("name"))
        
        data = (get_price_and_stock_details(item_variant, warehouse, price_list))
        data["item_name"] = item_variant.name
        data["attributes"] = []
        for attr in item_variant.get('attributes'):
            attribute_option = {}
            attribute_option["name"] = attr.attribute
            attribute_option["option"] = attr.attribute_value
            data["attributes"].append(attribute_option)
            
            if attr.attribute not in attr_sequence:
                attr_sequence.append(attr.attribute)
            if not attr_dict.get(attr.attribute):
                attr_dict.setdefault(attr.attribute, [])

            attr_dict[attr.attribute].append(attr.attribute_value)
        
        variant_list.append(data)    
        

    for i, attr in enumerate(attr_sequence):
        options.append({
            "name": attr,
            "visible": "True",
            "variation": "True",
            "position": i+1,
            "options": list(set(attr_dict[attr]))
        })        
    return variant_list, options, variant_item_name

def get_price_and_stock_details(item, warehouse, price_list):
    qty = frappe.db.get_value("Bin", {"item_code":item.get("item_code"), "warehouse": warehouse}, "actual_qty")
    price = frappe.db.get_value("Item Price", \
            {"price_list": price_list, "item_code":item.get("item_code")}, "price_list_rate")

    item_price_and_quantity = {
        "regular_price": "{0}".format(flt(price)) #only update regular price
    }

    if item.weight_per_unit:
        if item.weight_uom and item.weight_uom.lower() in ["kg", "g", "oz", "lb", "lbs"]:
            item_price_and_quantity.update({
                "weight": "{0}".format(get_weight_in_woocommerce_unit(item.weight_per_unit, item.weight_uom))
            })

    if item.stock_keeping_unit:
        item_price_and_quantity = {
        "sku": "{0}".format(item.stock_keeping_unit) 
    }
        
    if item.get("sync_qty_with_woocommerce"):
        item_price_and_quantity.update({
            "stock_quantity": "{0}".format(cint(qty) if qty else 0),
            "manage_stock": "True"
        })
    
    #rlavaud Do I need this???
    if item.woocommerce_variant_id:
        item_price_and_quantity["id"] = item.woocommerce_variant_id


    return item_price_and_quantity

def get_weight_in_grams(weight, weight_uom):
    convert_to_gram = {
        "kg": 1000,
        "lb": 453.592,
        "oz": 28.3495,
        "g": 1
    }

    return weight * convert_to_gram[weight_uom.lower()]

def get_weight_in_woocommerce_unit(weight, weight_uom):
    woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
    weight_unit = woocommerce_settings.weight_unit
    convert_to_gram = {
        "kg": 1000,
        "lb": 453.592,
        "lbs": 453.592,
        "oz": 28.3495,
        "g": 1
    }
    convert_to_oz = {
        "kg": 0.028,
        "lb": 0.062,
        "lbs": 0.062,
        "oz": 1,
        "g": 28.349
    }
    convert_to_lb = {
        "kg": 1000,
        "lb": 1,
        "lbs": 1,
        "oz": 16,
        "g": 0.453
    }
    convert_to_kg = {
        "kg": 1,
        "lb": 2.205,
        "lbs": 2.205,
        "oz": 35.274,
        "g": 1000
    }
    if weight_unit.lower() == "g":
        return weight * convert_to_gram[weight_uom.lower()]
        
    if weight_unit.lower() == "oz":
        return weight * convert_to_oz[weight_uom.lower()]
    
    if weight_unit.lower() == "lb"  or weight_unit.lower() == "lbs":
        return weight * convert_to_lb[weight_uom.lower()]
    
    if weight_unit.lower() == "kg":
        return weight * convert_to_kg[weight_uom.lower()]



def trigger_update_item_stock(doc, method):
    if doc.flags.via_stock_ledger_entry:
        woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
        if woocommerce_settings.woocommerce_url and woocommerce_settings.enable_woocommerce:
            update_item_stock(doc.item_code, woocommerce_settings, doc)

def update_item_stock_qty():
    woocommerce_settings = frappe.get_doc("woocommerce Settings", "woocommerce Settings")
    
    for item in frappe.get_all("Item", fields=["item_code"], filters={"sync_qty_with_woocommerce": '1', "disabled": ("!=", 1)}):
        try:
            update_item_stock(item.item_code, woocommerce_settings)
        except woocommerceError as e:
            make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
                request_data=item, exception=True)

        except Exception as e:
            if e.args[0] and e.args[0].startswith("402"):
                raise e
            else:
                make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
                    request_data=item, exception=True)

def update_item_stock(item_code, woocommerce_settings, bin=None):
    item = frappe.get_doc("Item", item_code)
    if item.sync_qty_with_woocommerce:
        if not item.woocommerce_product_id:
            make_woocommerce_log(title="WooCommerce ID missing", status="Error", method="sync_woocommerce_items", 
                message="Please sync WooCommerce IDs to ERP (missing for item {0})".format(item_code), request_data=item_code, exception=True)
        else:
            bin = get_bin(item_code, woocommerce_settings.warehouse)
            qty = bin.actual_qty
            for warehouse in woocommerce_settings.warehouses:
                _bin = get_bin(item_code, warehouse.warehouse)
                qty += _bin.actual_qty

            # bugfix #1582: variant control from WooCommerce, not ERPNext
            if item.woocommerce_variant_id > 0:
                item_data, resource = get_product_update_dict_and_resource(item.woocommerce_product_id, item.woocommerce_variant_id, is_variant=True, actual_qty=qty)
            else:
                item_data, resource = get_product_update_dict_and_resource(item.woocommerce_product_id, item.woocommerce_variant_id, actual_qty=qty)
            try:
                #make_woocommerce_log(title="Update stock of {0}".format(item.barcode), status="Started", method="update_item_stock", message="Resource: {0}, data: {1}".format(resource, item_data))
                put_request(resource, item_data)
            except requests.exceptions.HTTPError as e:
                if e.args[0] and e.args[0].startswith("404"):
                    make_woocommerce_log(title=e.message, status="Error", method="update_item_stock", message=frappe.get_traceback(),
                        request_data=item_data, exception=True)
                    disable_woocommerce_sync_for_item(item)
                else:
                    raise e


def get_product_update_dict_and_resource(woocommerce_product_id, woocommerce_variant_id, is_variant=False, actual_qty=0):
    item_data = {}
    item_data["stock_quantity"] = "{0}".format(cint(actual_qty))
    item_data["manage_stock"] = "1"
    
    if is_variant:
        resource = "products/{0}/variations/{1}".format(woocommerce_product_id,woocommerce_variant_id)
    else: #simple item 
        resource = "products/{0}".format(woocommerce_product_id)
    
    return item_data, resource

def add_w_id_to_erp():
    # purge WooCommerce IDs so that there cannot be any conflict
    purge_ids = """UPDATE `tabItem`
            SET `woocommerce_product_id` = NULL, `woocommerce_variant_id` = NULL;"""
    frappe.db.sql(purge_ids)
    frappe.db.commit()

    # loop through all items on WooCommerce and get their IDs (matched by barcode)
    woo_items = get_woocommerce_items()
    make_woocommerce_log(title="Syncing IDs", status="Started", method="add_w_id_to_erp", message='Item: {0}'.format(woo_items),
        request_data={}, exception=True)
    for woocommerce_item in woo_items:
        update_item = """UPDATE `tabItem`
            SET `woocommerce_product_id` = '{0}'
            WHERE `barcode` = '{1}';""".format(woocommerce_item.get("id"), woocommerce_item.get("sku"))
        frappe.db.sql(update_item)
        frappe.db.commit()
        for woocommerce_variant in get_woocommerce_item_variants(woocommerce_item.get("id")):
            update_variant = """UPDATE `tabItem`
                SET `woocommerce_variant_id` = '{0}', `woocommerce_product_id` = '{1}'
                WHERE `barcode` = '{2}';""".format(woocommerce_variant.get("id"), woocommerce_item.get("id"), woocommerce_variant.get("sku"))
            frappe.db.sql(update_variant)
            frappe.db.commit()
    make_woocommerce_log(title="IDs synced", status="Success", method="add_w_id_to_erp", message={},
        request_data={}, exception=True)
