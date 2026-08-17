from odoo import api, fields, models, tools
from odoo.fields import Domain


class StockAverageCostReport(models.AbstractModel):
    _inherit = 'stock.avco.report'

    _group_total_fields = {
        'added_value:sum': 'added_value',
    }

    categ_id = fields.Many2one(
        'product.category',
        string='Product Category',
        readonly=True,
    )
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW stock_avco_report AS (
                SELECT
                    sm.id AS id,
                    sm.product_id,
                    sm.date,
                    picking.user_id,
                    sm.company_id,
                    sm.reference,
                    CASE WHEN sm.is_in THEN sm.value ELSE -sm.value END AS value,
                    CASE WHEN sm.is_in THEN sm.quantity ELSE -sm.quantity END AS quantity,
                    'stock.move' AS res_model_name,
                    'Operation' AS description,
                    pt.categ_id AS categ_id
                FROM stock_move sm
                LEFT JOIN stock_picking picking ON sm.picking_id = picking.id
                LEFT JOIN product_product pp ON sm.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_category pc ON pt.categ_id = pc.id
                LEFT JOIN res_company company ON sm.company_id = company.id
                WHERE
                    sm.state = 'done'
                    AND (sm.is_in = TRUE OR sm.is_out = TRUE)
                    AND (
                        (
                            pt.categ_id IS NOT NULL
                            AND pc.property_cost_method ->> company.id::text IN ('fifo', 'average')
                        )
                        OR (
                            pt.categ_id IS NULL
                            OR (
                                pc.property_cost_method IS NULL
                                OR pc.property_cost_method ->> company.id::text IS NULL
                            )
                            AND company.cost_method IN ('fifo', 'average')
                        )
                    )
                UNION ALL
                SELECT
                    -pv.id AS id,
                    pv.product_id,
                    pv.date,
                    pv.user_id,
                    pv.company_id,
                    'Adjustment' AS reference,
                    pv.value,
                    0 AS quantity,
                    'product.value' AS res_model_name,
                    pv.description,
                    pt.categ_id AS categ_id
                FROM product_value pv
                LEFT JOIN product_product pp ON pv.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE pv.move_id IS NULL
            )
        """)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        field_descriptions = super().fields_get(allfields, attributes)
        if not attributes or 'aggregator' in attributes:
            for field_name in self._group_total_fields.values():
                if field_name in field_descriptions:
                    field_descriptions[field_name]['aggregator'] = 'sum'
        return field_descriptions

    @api.model
    def formatted_read_group(
        self,
        domain,
        groupby=(),
        aggregates=(),
        having=(),
        offset=0,
        limit=None,
        order=None,
    ):
        computed_aggregates = [
            aggregate for aggregate in aggregates
            if aggregate in self._group_total_fields
        ]
        if not computed_aggregates:
            return super().formatted_read_group(
                domain,
                groupby,
                aggregates,
                having=having,
                offset=offset,
                limit=limit,
                order=order,
            )

        stored_aggregates = [
            aggregate for aggregate in aggregates
            if aggregate not in self._group_total_fields
        ]
        if order:
            computed_order_fields = {
                *self._group_total_fields,
                *self._group_total_fields.values(),
            }
            order = ', '.join(
                order_part for order_part in order.split(',')
                if order_part.strip().split()[0] not in computed_order_fields
            ) or None
        groups = super().formatted_read_group(
            domain,
            groupby,
            stored_aggregates,
            having=having,
            offset=offset,
            limit=limit,
            order=order,
        )
        base_domain = Domain(domain)
        if tuple(groupby) == ('product_id',):
            product_ids = [
                group['product_id'][0]
                for group in groups
                if group['product_id']
            ]
            records = self.search(
                base_domain & Domain('product_id', 'in', product_ids)
            )
            records_by_product = records.grouped('product_id')
            for aggregate in computed_aggregates:
                records.mapped(self._group_total_fields[aggregate])
            for group in groups:
                product_id = group['product_id'][0] if group['product_id'] else False
                product_records = records_by_product.get(
                    self.env['product.product'].browse(product_id), self.browse()
                )
                for aggregate in computed_aggregates:
                    field_name = self._group_total_fields[aggregate]
                    group[aggregate] = sum(product_records.mapped(field_name))
            return groups

        for group in groups:
            records = self.search(base_domain & Domain(group['__extra_domain']))
            for aggregate in computed_aggregates:
                field_name = self._group_total_fields[aggregate]
                group[aggregate] = sum(records.mapped(field_name))
        return groups
