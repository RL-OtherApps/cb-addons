# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'CB Hash Search Account Purchase',
    'summary': """
        Allow to use hash search with purchase orders""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Creu Blanca',
    'website': 'www.creublanca.es',
    'depends': [
        'hash_search_purchase',
    ],
    'data': [
        'data/purchase_order_label.xml',
    ],
}
