from __future__ import unicode_literals
import frappe
from frappe import _
from .exceptions import woocommerceError
from frappe.utils import get_request_session, get_datetime, get_time_zone
from woocommerce import API
from .utils import make_woocommerce_log
import requests
from frappe.utils import cint

_per_page = 100

# def check_api_call_limit(response):
#    """
#        This article will show you how to tell your program to take small pauses
#        to keep your app a few API calls shy of the API call limit and
#        to guard you against a 429 - Too Many Requests error.
#
#        ref : https://docs.woocommerce.com/api/introduction/api-call-limit
#    """
#    if response.headers.get("HTTP_X_woocommerce_SHOP_API_CALL_LIMIT") == 39:
#        time.sleep(10)    # pause 10 seconds


def get_woocommerce_settings():
    d = frappe.get_doc("WooCommerce Config")

    if d.woocommerce_url:
        d.api_secret = d.get_password(fieldname="api_secret")
        return d.as_dict()

    else:
        frappe.throw(
            _("woocommerce store URL is not configured on WooCommerce Config"),
            woocommerceError,
        )


def get_request_request(path, settings=None, params=None):
    if not settings:
        settings = get_woocommerce_settings()

    wcapi = API(
        url=settings["woocommerce_url"],
        consumer_key=settings["api_key"],
        consumer_secret=settings["api_secret"],
        verify_ssl=settings["verify_ssl"],
        wp_api=True,
        version="wc/v3",
        timeout=1000,
    )
    r = wcapi.get(path, params=params)

    # r.raise_for_status()
    # manually raise for status to get more info from error (message details)
    if r.status_code != requests.codes.ok:
        make_woocommerce_log(
            title="WooCommerce get error {0}".format(r.status_code),
            status="Error",
            method="get_request",
            message="{0}: {1}".format(r.url, r.json()),
            request_data="not defined",
            exception=True,
        )
    return r


def get_request(path, settings=None):
    return get_request_request(path, settings).json()


def post_request(path, data):
    settings = get_woocommerce_settings()

    wcapi = API(
        url=settings["woocommerce_url"],
        consumer_key=settings["api_key"],
        consumer_secret=settings["api_secret"],
        verify_ssl=settings["verify_ssl"],
        wp_api=True,
        version="wc/v3",
        timeout=1000,
    )

    r = wcapi.post(path, data)

    # r.raise_for_status()
    # manually raise for status to get more info from error (message details)
    if r.status_code != requests.codes.ok:
        make_woocommerce_log(
            title="WooCommerce post error {0}".format(r.status_code),
            status="Error",
            method="post_request",
            message="{0}: {1}".format(r.url, r.json()),
            request_data=data,
            exception=True,
        )
    return r.json()


def put_request(path, data):
    settings = get_woocommerce_settings()

    wcapi = API(
        url=settings["woocommerce_url"],
        consumer_key=settings["api_key"],
        consumer_secret=settings["api_secret"],
        verify_ssl=settings["verify_ssl"],
        wp_api=True,
        version="wc/v3",
        timeout=5000,
    )
    # frappe.log_error("{0} data: {1}".format(path, data))
    r = wcapi.put(path, data)

    # r.raise_for_status()
    # manually raise for status to get more info from error (message details)
    if r.status_code != requests.codes.ok:
        make_woocommerce_log(
            title="WooCommerce put error {0}".format(r.status_code),
            status="Error",
            method="put_request",
            message="{0}: {1}".format(r.url, r.json()),
            request_data=data,
            exception=True,
        )

    return r.json()


def delete_request(path):
    settings = get_woocommerce_settings()

    wcapi = API(
        url=settings["woocommerce_url"],
        consumer_key=settings["api_key"],
        consumer_secret=settings["api_secret"],
        verify_ssl=settings["verify_ssl"],
        wp_api=True,
        version="wc/v3",
        timeout=1000,
    )
    r = wcapi.post(path)

    r.raise_for_status()


def get_woocommerce_url(path, settings):
    return settings["woocommerce_url"]


def get_header(settings):
    header = {"Content-Type": "application/json"}
    return header


"""    if settings['app_type'] == "Private":
        return header
    else:
        header["X-woocommerce-Access-Token"] = settings['access_token']
        return header
"""


def get_filtering_condition(only_query_value=False):
    woocommerce_settings = get_woocommerce_settings()
    if woocommerce_settings.last_sync_datetime:
        last_sync_datetime = get_datetime(
            woocommerce_settings.last_sync_datetime
        ).isoformat()
        if only_query_value:
            return last_sync_datetime
        # uncomment for live
        return "modified_after={0}".format(last_sync_datetime)
    return ""


def get_country():
    return get_request("/admin/countries.json")["countries"]


def get_woocommerce_items(ignore_filter_conditions=False):
    woocommerce_products = []

    def extend_if_ok(response):
        if response.status_code == requests.codes.ok:
            woocommerce_products.extend(response.json())

    filter_condition = ""
    if not ignore_filter_conditions:
        filter_condition = get_filtering_condition(True)
        if cint(frappe.get_value("WooCommerce Config", "WooCommerce Config", "sync_only_published")) == 1:
            filter_condition += "&status=publish"

    response = get_request_request(
        "products", params={"per_page": _per_page, "after": filter_condition}
    )
    extend_if_ok(response)

    total_pages = int(response.headers.get("X-WP-TotalPages") or 1)
    for page_idx in range(1, total_pages):
        response = get_request_request(
            "products",
            params={
                "per_page": _per_page,
                "page": page_idx + 1,
                "after": filter_condition,
            },
        )
        extend_if_ok(response)

    return woocommerce_products


def get_woocommerce_item_variants(woocommerce_product_id):
    woocommerce_product_variants = []

    def extend_if_ok(response):
        if response.status_code == requests.codes.ok:
            woocommerce_product_variants.extend(response.json())

    filter_condition = ""

    response = get_request_request(
        "products/{0}/variations?per_page={1}&{2}".format(
            woocommerce_product_id, _per_page, filter_condition
        )
    )
    extend_if_ok(response)

    total_pages = int(response.headers.get("X-WP-TotalPages") or 1)
    for page_idx in range(1, total_pages):
        response = get_request_request(
            "products/{0}/variations?per_page={1}&page={2}&{3}".format(
                woocommerce_product_id, _per_page, page_idx + 1, filter_condition
            )
        )
        extend_if_ok(response)

    return woocommerce_product_variants


def get_woocommerce_item_image(woocommerce_product_id):
    return get_request("products/{0}".format(woocommerce_product_id))["images"]


def get_woocommerce_tax(woocommerce_tax_id):
    return get_request("taxes/{0}".format(woocommerce_tax_id))


def get_woocommerce_customer(woocommerce_customer_id):
    return get_request("customers/{0}".format(woocommerce_customer_id))


def get_woocommerce_orders(order_status):
    woocommerce_orders = []

    def extend_if_ok(response):
        if response.status_code == requests.codes.ok:
            woocommerce_orders.extend(response.json())

    response = get_request_request(
        "orders",
        params={
            "per_page": _per_page,
            "status": order_status,
        },
    )
    extend_if_ok(response)

    total_pages = int(response.headers.get("X-WP-TotalPages") or 1)
    for page_idx in range(1, total_pages):
        response = get_request_request(
            "orders",
            params={
                "per_page": _per_page,
                "page": page_idx + 1,
                "status": order_status,
            },
        )
        extend_if_ok(response)

    return woocommerce_orders


def get_woocommerce_customers(ignore_filter_conditions=False):
    woocommerce_customers = []

    def extend_if_ok(response):
        if response.status_code == requests.codes.ok:
            woocommerce_customers.extend(response.json())

    if not ignore_filter_conditions:
        filter_condition = get_filtering_condition()

        response = get_request_request(
            "customers?per_page={0}&{1}".format(_per_page, filter_condition)
        )
        extend_if_ok(response)

        total_pages = int(response.headers.get("X-WP-TotalPages") or 1)
        for page_idx in range(1, total_pages):
            response = get_request_request(
                "customers?per_page={0}&page={1}&{2}".format(
                    _per_page, page_idx + 1, filter_condition
                )
            )
            extend_if_ok(response)

    return woocommerce_customers
