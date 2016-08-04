# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.exceptions import except_orm


class Priority(models.Model):
    """Priorities represent the timeframe to do tasks.
    It can represent timeboxes, deadlines, milestones
    TODO : add milestone
    """
    _name = 'anytracker.priority'
    _description = 'Priority of Ticket by method'
    _order = 'method_id, seq'

    name = fields.Char(
        'Priority name',
        required=True,
        size=64,
        translate=True)
    description = fields.Text(
        'Priority description',
        translate=True)
    seq = fields.Integer(
        'Priority',
        help='a low value is higher priority')
    active = fields.Boolean(
        'Active',
        default=True,
        help='if check, this object is always available')
    method_id = fields.Many2one(
        'anytracker.method',
        string='Method',
        required=True,
        ondelete='cascade')
    deadline = fields.Boolean(
        'Force to choose a deadline on the ticket?')
    date = fields.Date(
        'Milestone')
    default = fields.Boolean(
        "Default",
        help="Default priority for new tickets")


class Ticket(models.Model):
    _inherit = 'anytracker.ticket'

    @api.depends('priority_id')
    def _get_priority(self):
        for t in self:
            t.priority = t.priority_id.seq if t.priority_id else None

    @api.multi
    @api.onchange('priority_id')
    def onchange_priority(self):
        if self.priority_id.deadline:
            self.has_deadline = True
        else:
            self.has_deadline = False

    @api.model
    def create(self, values):
        """select the default priority
        """
        METHOD = self.env['anytracker.method']
        PRIORITY = self.env['anytracker.priority']
        if not values.get('priority_id'):
            if values.get('parent_id'):
                method = self.browse(values.get('parent_id')).method_id
            else:
                method = METHOD.browse(values['method_id'])
            priorities = PRIORITY.search([
                ('method_id', '=', method.id),
                ('default', '=', True)])
            if len(priorities) > 1:
                raise except_orm(
                    _('Anytracker Configuration Error'),
                    _("Two priorities are configured as the default one "
                      "in the '{}' method".format(method.name)))
            if len(priorities) == 1:
                values['priority_id'] = priorities[0].id
        return super(Ticket, self).create(values)

    has_deadline = fields.Boolean(
        'priority_id.deadline',
        readonly=True,
        type="boolean")
    deadline = fields.Date(
        'Deadline')
    priority_id = fields.Many2one(
        'anytracker.priority',
        'Priority')
    priority = fields.Integer(
        compute='_get_priority',
        string='Priority',
        store=True)


class Method(models.Model):
    _inherit = 'anytracker.method'

    priority_ids = fields.One2many(
        'anytracker.priority',
        'method_id',
        string='Priorities',
        copy=True,
        help="The priorities associated to this method")
