#!/usr/bin/env python3
"""
Fetch Odoo data and update dashboard JSON files
Run locally or via GitHub Actions (with secrets configured)
"""
import xmlrpc.client
import ssl
import json
import os
from datetime import datetime

# Odoo configuration - use env vars in GitHub Actions
ssl._create_default_https_context = ssl._create_unverified_context

ODOO_URL = os.environ.get('ODOO_URL', 'https://odoo-ss6o.srv1069133.hstgr.cloud')
ODOO_DB = os.environ.get('ODOO_DB', 'kitchen_dunya')
ODOO_USER = os.environ.get('ODOO_USER', 'msme.rs786@gmail.com')
ODOO_PASS = os.environ.get('ODOO_PASS', 'sales.kitchendunya53')

def main():
    print(f"Connecting to Odoo: {ODOO_URL}")
    
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    print(f"Authenticated as UID: {uid}")
    
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    # Sales data
    domain = [['date', '<=', '2026-06-30'], ['parent_state', '=', 'posted'], ['company_id', '=', 3]]
    move_line_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move.line', 'search', [domain])
    entries = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move.line', 'read', 
        [move_line_ids], {'fields': ['account_id', 'debit', 'credit', 'date']})
    
    from collections import defaultdict
    sales_by_month = defaultdict(float)
    tax_received = 0
    tax_paid = 0
    
    for e in entries:
        acct = e.get('account_id')
        if acct and isinstance(acct, list):
            if 'Sales' in str(acct[1]) and (e.get('credit', 0) or 0) > 0:
                month = e.get('date', '')[:7]
                sales_by_month[month] += e.get('credit', 0) or 0
            if 'Sales Tax' in str(acct[1]):
                tax_received += e.get('credit', 0) or 0
                tax_paid += e.get('debit', 0) or 0
    
    total_sales = sum(sales_by_month.values())
    
    # Orders
    order_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'sale.order', 'search', [[('company_id', '=', 3)]])
    orders = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'sale.order', 'read', 
        [order_ids], {'fields': ['state']})
    total_orders = len([o for o in orders if o.get('state') in ['sale', 'done']])
    
    # Stock
    products = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'product.product', 'search_read',
        [(), ['id', 'name']], {'limit': 100})
    
    stock_data = []
    for p in products:
        pid = p['id']
        quants = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'stock.quant', 'search_read',
            [[['product_id', '=', pid], ['location_id.usage', '=', 'internal']]],
            {'fields': ['quantity'], 'limit': 10})
        total_qty = sum(q['quantity'] for q in quants)
        if total_qty > 0:
            stock_data.append({'name': p['name'][:30], 'qty': int(total_qty)})
    
    stock_data.sort(key=lambda x: -x['qty'])
    
    # Save JSON files
    now = datetime.now().isoformat()
    
    sales_json = {
        'total': round(total_sales, 2),
        'orders': total_orders,
        'months': sorted(sales_by_month.keys()),
        'amounts': [round(sales_by_month[m], 2) for m in sorted(sales_by_month.keys())],
        'lastUpdated': now
    }
    
    tax_json = {
        'received': round(tax_received, 2),
        'paid': round(tax_paid, 2),
        'liability': round(tax_received - tax_paid, 2),
        'lastUpdated': now
    }
    
    stock_json = {
        'totalItems': len(stock_data),
        'topProducts': stock_data[:15],
        'lastUpdated': now
    }
    
    # Write files
    with open('data/sales.json', 'w') as f:
        json.dump(sales_json, f, indent=2)
    
    with open('data/tax.json', 'w') as f:
        json.dump(tax_json, f, indent=2)
    
    with open('data/stock.json', 'w') as f:
        json.dump(stock_json, f, indent=2)
    
    print(f"✓ Total Sales: Rs. {total_sales:,.2f}")
    print(f"✓ Total Orders: {total_orders}")
    print(f"✓ Tax Liability: Rs. {tax_received - tax_paid:,.2f}")
    print(f"✓ Stock Items: {len(stock_data)}")

if __name__ == '__main__':
    main()
