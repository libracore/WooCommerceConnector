// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("woocommerceconnector.woocommerce_config");

frappe.ui.form.on("WooCommerce Config", {
    onload: function(frm, dt, dn){
        frappe.call({
            method:"woocommerceconnector.woocommerceconnector.doctype.woocommerce_config.woocommerce_config.get_series",
            callback:function(r){
                $.each(r.message, function(key, value){
                    set_field_options(key, value)
                })
            }
        })
    },
    app_type: function(frm, dt, dn) {
        frm.toggle_reqd("api_key", (frm.doc.app_type == "Private"));
        frm.toggle_reqd("password", (frm.doc.app_type == "Private"));
    },
    refresh: function(frm){
		// set filters
		frm.fields_dict["warehouse"].get_query = function(doc) {
            return {
                filters:{
                    "company": doc.company,
                    "is_group": "No"
                }
            }
        }

        frm.fields_dict["taxes"].grid.get_field("tax_account").get_query = function(doc, dt, dn){
            return {
                "query": "erpnext.controllers.queries.tax_account_query",
                "filters": {
                    "account_type": ["Tax", "Chargeable", "Expense Account"],
                    "company": doc.company
                }
            }
        }

        frm.fields_dict["cash_bank_account"].get_query = function(doc) {
            return {
                filters: [
                    ["Account", "account_type", "in", ["Cash", "Bank"]],
                    ["Account", "root_type", "=", "Asset"],
                    ["Account", "is_group", "=",0],
                    ["Account", "company", "=", doc.company]
                ]
            }
        }

        frm.fields_dict["cost_center"].get_query = function(doc) {
            return {
                filters:{
                    "company": doc.company,
                    "is_group": "No"
                }
            }
        }
		
		// toggle fields
        if(!frm.doc.__islocal && frm.doc.enable_woocommerce === 1){
            frm.toggle_reqd("price_list", true);
            frm.toggle_reqd("warehouse", true);
            frm.toggle_reqd("taxes", true);
            frm.toggle_reqd("company", true);
            frm.toggle_reqd("cost_center", true);
            frm.toggle_reqd("cash_bank_account", true);
            frm.toggle_reqd("sales_order_series", true);
            frm.toggle_reqd("customer_group", true);
            
            frm.toggle_reqd("sales_invoice_series", frm.doc.sync_sales_invoice);
            frm.toggle_reqd("delivery_note_series", frm.doc.sync_delivery_note);

            frm.add_custom_button(__('Sync WooCommerce'), function() {
                frappe.call({
                    method:"woocommerceconnector.api.sync_woocommerce",
                })
            }).addClass("btn-primary");
            
            frm.add_custom_button(__("Sync WooCommerce IDs to ERP"), function(){
                frappe.call({
                    method:"woocommerceconnector.api.sync_woocommerce_ids",
                })
            })
        }

		// add buttons
        frm.add_custom_button(__("WooCommerce Log"), function(){
            frappe.set_route("List", "woocommerce Log");
        })
        
        frm.add_custom_button(__("Reset Last Sync Date"), function(){
            frappe.prompt([
                    {"fieldtype": "Datetime", "label": __("Date"), "fieldname": "last_sync_date", "reqd": 1}  
                ],
                function(values){
                    cur_frm.set_value("last_sync_datetime", values.last_sync_date);
                    cur_frm.save();
                },
                __("Reset Last Sync Date"),
                "OK"
            );
        })

        frappe.call({
            method: "woocommerceconnector.api.get_log_status",
            callback: function(r) {
                if(r.message){
                    frm.dashboard.set_headline_alert(r.message.text, r.message.alert_class)
                }
            }
        })
    }
});