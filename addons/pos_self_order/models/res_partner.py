# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    self_order_preset_id = fields.Many2one(
        'pos.preset',
        string='Self-Order Preset',
        help='Preset used to lock self-order pricing and workflow for this customer.',
    )

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        return False

    @api.model
    def _load_pos_self_data_read(self, records, config):
        """ Read specific fields from the given records """
        fields = [
            'id', 'name', 'email', 'phone', 'street', 'city', 'zip',
            'country_id', 'state_id', 'write_date', 'property_product_pricelist',
            'self_order_preset_id',
        ]
        records = records.read(fields, load=False)
        return records or []
