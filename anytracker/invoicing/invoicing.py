# coding: utf-8
from openerp import models, fields, api, _
from openerp.exceptions import except_orm
import logging
from datetime import datetime, timedelta
from openerp import SUPERUSER_ID

logger = logging.getLogger(__file__)


class Ticket(models.Model):
    """ Allow to invoice a single ticket
    """

    _inherit = 'anytracker.ticket'

    @api.multi
    def create_analytic_line(self):
        """ Create an analytic line for each ticket
        """
        result = []
        ANALINE = self.env['account.analytic.line']
        for t in self:
            if t.analytic_line_id:
                continue
            if not t.project_id.product_id:
                raise except_orm(
                    _('Error'),
                    _("To be able to invoice a ticket, "
                      "you should set a product "
                      "on the corresponding project"))
            if not t.project_id.analytic_account_id:
                raise except_orm(
                    _('Error'),
                    _("To be able to invoice a ticket, "
                      "you should set an analytic account "
                      "on the corresponding project"))
            if not t.rating:
                logger.warn(("Ticket #%s could not be invoiced "
                             "because it has no rating"), t.number)
                continue
            if t.type.has_children:
                raise except_orm(
                    _('Error'),
                    _("Ticket #%s is a project or node. "
                      "It cannot be invoiced") % t.number)
            # on OCB the general account is not mandatory,
            # but let's be compatible with openerp
            gen_account = t.project_id.product_id.property_account_expense
            if not gen_account and t.project_id.product_id.categ_id:
                gen_account = (t.project_id
                               .product_id
                               .categ_id
                               .property_account_expense_categ)
            if not gen_account:
                raise except_orm(
                    'Error',
                    ("No expense account defined on the product (or category)"
                     " configured in your anytracker project"))
            if t.assigned_user_id:
                user_id = t.assigned_user_id.id
            elif t.rating_ids:
                user_id = t.rating_ids[0].user_id.id
            else:
                user_id = self.env.user.id
            line_data = {
                'name': 'Ticket %s: %s' % (t.number, t.name),
                'ref': 'Ticket %s' % t.number,
                'amount': 1.0,
                'unit_amount': t.rating,
                'to_invoice': t.project_id.analytic_account_id.to_invoice.id,
                'account_id': t.project_id.analytic_account_id.id,
                'product_id': t.project_id.product_id.id,
                'journal_id': t.project_id.analytic_journal_id.id,
                'general_account_id': gen_account.id,
                'user_id': user_id,
            }
            if t.priority_id and t.priority_id.discount_id:
                line_data['to_invoice'] = t.priority_id.discount_id.id
            analine = ANALINE.create(line_data)
            analine.write(analine.on_change_unit_amount(
                line_data['product_id'], line_data['unit_amount'],
                None, journal_id=line_data['journal_id'])[0]['value'])
            t.write({'analytic_line_id': analine.id})
            result.append(analine.id)
        return result

    def cron(self):
        super(Ticket, self).cron()
        # tickets to invoice
        yesterday = (datetime.now() - timedelta(1)
                     ).strftime("%Y-%m-%d %H:%M:%S")
        tickets = self.search([
            ('analytic_line_id', '=', False),
            ('progress', '=', 100.0),
            ('rating', '!=', 0.0),
            ('active', '=', True),
            ('write_date', '<=', yesterday),
            ('project_id.analytic_journal_id', '!=', False),
            ('project_id.product_id', '!=', False),
            ('project_id.analytic_account_id', '!=', False),
            ('type.has_children', '=', False),
        ])
        tickets.create_analytic_line()

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        'Analytic account / project',
        help=(u"Choose the analytic account or project on which "
              u"to create analytic lines to invoice"))
    analytic_line_id = fields.Many2one(
        'account.analytic.line',
        'Analytic line',
        help=(u"The analytic line used to invoice the ticket"))
    product_id = fields.Many2one(
        'product.product',
        'Product to invoice',
        help=(u"The product to invoice"))
    analytic_journal_id = fields.Many2one(
        'account.analytic.journal',
        'Analytic journal',
        help=(u"Analytic journal to use when invoicing"))


class Bouquet(models.Model):
    """ Allow to invoice all the tickets of the bouquet
    """
    _inherit = "anytracker.bouquet"

    @api.multi
    def create_analytic_lines(self):
        """ Create analytic lines of for all tickets of the bouquet
        """
        for bouquet in self:
            bouquet.ticket_ids.create_analytic_line()


class Priority(models.Model):
    """Add invoicing ratio to priorities
    """
    _inherit = 'anytracker.priority'

    discount_id = fields.Many2one(
        'hr_timesheet_invoice.factor', 'Ratio',
        help=u'set the invoicing ratio for tickets with this priority')


class account_analytic_line(models.Model):
    """ Allow a customer to search analytic line by date
    (related to commit d6106d1aa13d)
    """
    _inherit = "account.analytic.line"

    def search(self, cr, uid, args, offset=0, limit=None,
               order=None, context=None, count=False):
        if len(args) == 1 and len(args[0]) == 3 and args[0][0] == 'date':
            uid = SUPERUSER_ID
        return super(account_analytic_line, self).search(
            cr, uid, args, offset=offset, limit=limit,
            order=order, context=context, count=count)
