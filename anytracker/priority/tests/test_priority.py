from anybox.testing.openerp import SharedSetupTransactionCase
from os.path import join
from openerp.osv import orm


class TestPriority(SharedSetupTransactionCase):

    _module_ns = 'anytracker'
    _data_files = (join('..', '..', 'tests', 'data.xml'),)

    @classmethod
    def initTestData(cls):
        super(TestPriority, cls).initTestData()
        cls.ref = classmethod(lambda cls, xid: cls.env.ref(xid).id)
        cls.TICKET = cls.env['anytracker.ticket']
        USER = cls.env['res.users']
        cls.PRIORITY = cls.env['anytracker.priority']

        cls.prio_urgent = cls.ref('anytracker.test_prio_urgent')
        cls.prio_prio = cls.ref('anytracker.test_prio_prio')
        cls.prio_normal = cls.ref('anytracker.test_prio_normal')
        cls.customer_id = USER.create(
            {'name': 'Customer',
             'login': 'customer',
             'groups_id': [(6, 0,
                           [cls.ref('anytracker.group_customer')])]}
        ).id

    def test_priority(self):
        # create a project and a ticket
        project = self.TICKET.create({
            'name': 'test project',
            'participant_ids': [(6, 0, [self.customer_id])],
            'method_id': self.ref('anytracker.method_test')})
        ticket = self.TICKET.create({
            'name': 'Test simple ticket',
            'parent_id': project.id})
        # we check that a default priority has been set
        self.assertEquals(ticket.priority_id.name, 'NORMAL')
        # the customer sets another priority
        ticket.sudo(self.customer_id).write({'priority_id': self.prio_urgent})
        self.assertEquals(ticket.priority_id.seq, 30)
        self.assertEquals(ticket.priority, 30)
        self.assertEquals(ticket.priority_id.name, 'URGENT')
        ticket.sudo(self.customer_id).write({'priority_id': self.prio_prio})
        self.assertEquals(ticket.priority_id.seq, 20)
        self.assertEquals(ticket.priority, 20)
        # we no default priority we have nothing on the ticket
        self.PRIORITY.browse(self.prio_normal).write({'default': False})
        ticket = self.TICKET.create({
            'name': 'Test simple ticket with no default priorities',
            'parent_id': project.id})
        self.assertEquals(ticket.priority_id.id, False)
        self.assertEquals(ticket.priority, False)
        # with two default priorities we get a config error
        self.PRIORITY.browse(self.prio_normal).write({'default': True})
        self.PRIORITY.browse(self.prio_prio).write({'default': True})
        self.assertRaises(
            orm.except_orm,
            self.TICKET.create,
            {'name': 'Test simple ticket with 2 default priorities',
             'parent_id': project.id})
        # check order
        self.PRIORITY.browse(self.prio_prio).write({'default': False})
        self.PRIORITY.browse(self.prio_normal).write(
            {'default': True, 'seq': -1})
        ticket = self.TICKET.create({
            'name': 'Test simple ticket with negative priority',
            'parent_id': project.id})
        tickets = self.TICKET.search([
            ('method_id', '=', self.ref('anytracker.method_test')),
            ('type', '=', 'ticket')])
        self.assertEquals([t.priority for t in tickets], [20, 0, -1])
