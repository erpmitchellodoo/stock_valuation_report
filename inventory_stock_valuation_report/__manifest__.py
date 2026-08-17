{
    'name': 'Stock Valuation Report',
    'version': '19.0.1.2.7',
    'category': 'Inventory/Inventory',
    'summary': 'Custom stock valuation reporting menu and list view',
     "author": "Mitchel Admin",
    "maintainer": "Mitchel Admin",
    "support": "erpmitchellodoo@gmail.com",
    "license": "LGPL-3",
    "price": 0.0,
    "currency": "EUR",
    'depends': [
        'stock_account',
        'mrp',
    ],
    'data': [
        'views/stock_valuation_report_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
