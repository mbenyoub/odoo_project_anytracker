from anybox.testing.openerp import SharedSetupTransactionCase


class TestBouquets(SharedSetupTransactionCase):

    @classmethod
    def initTestData(cls):
        super(TestBouquets, cls).initTestData()
        cls.ref = classmethod(lambda cls, xid: cls.env.ref(xid).id)
        cls.TICKET = cls.env['anytracker.ticket']
        cls.BOUQUET = cls.env['anytracker.bouquet']
        cls.ticket_obj = cls.registry['anytracker.ticket']
        cls.bouquet_obj = cls.registry['anytracker.bouquet']
        USER = cls.env['res.users']

        cls.member_id = USER.create({
            'name': 'anytracker member',
            'login': 'at.user',
            'groups_id': [(6, 0, [cls.ref('anytracker.group_member')])],
        }).id
        cls.customer_id = USER.create({
            'name': "anytracker customer",
            'login': 'at.cust',
            'groups_id': [(6, 0, [cls.ref('anytracker.group_customer')])],
        }).id
        cls.project = cls.TICKET.create({
            'name': "Main test project",
            'method_id': cls.ref('anytracker.method_scrum'),
            'participant_ids': [(6, 0, [cls.member_id, cls.customer_id])],
        })
        cls.ticket1 = cls.TICKET.create({
            'name': "First ticket",
            'parent_id': cls.project.id,
        })
        cls.ticket2 = cls.TICKET.create({
            'name': "Second ticket",
            'parent_id': cls.project.id,
        })
        cls.tickets = cls.ticket1 + cls.ticket2
        cls.bouquet = cls.BOUQUET.create({
            'name': u"Un bouquet ?",
            'ticket_ids': [(6, 0, cls.tickets.ids)]})

        cls.admin_id = cls.uid

    def test_create_read(self):
        self.assertRecord(self.bouquet_obj, self.bouquet.id,
                          {'ticket_ids': set(self.tickets.ids),
                           'nb_tickets': len(self.tickets.ids),
                           'project_ids': set([self.project]),
                           }, list_to_set=True)

    def test_create_read_perm(self):
        """Switch to non-privileged user to check access."""
        for uid in (self.member_id, self.customer_id):
            self.uid = uid
            # if this fails, fix the main part of Anytracker first
            # (no other unit tests at this time of writing):
            self.assertUniqueWithValues(self.ticket_obj,
                                        [('name', '=', "First ticket")],
                                        {'parent_id': self.project.id})

            # checking both search and read perms in one shot:
            self.assertUniqueWithValues(self.bouquet_obj,
                                        [], {'name': u"Un bouquet ?"})

    def test_read_perm_non_participating(self):
        # first, let's remove our 2 users from the related project
        self.project.sudo(self.admin_id).write({
            'participant_ids': [(6, 0, [])]})

        self.uid = self.member_id
        self.assertNoRecord(self.bouquet_obj, [])

    def test_read_perm_participating_mixed(self):
        """A user participating in any project related to the bouquet
        must have right perm.
        """
        project = self.TICKET.create({
            'name': "Another Project",  # no participants
            'method_id': self.ref('anytracker.method_scrum')})
        self.ticket1.sudo().write({'parent_id': project.id})

        # testing the project_ids function field while we're at it
        self.assertRecord(
            self.bouquet_obj,
            self.bouquet.id,
            {'project_ids': set([self.project, project])},
            list_to_set=True)

        for uid in (self.member_id, self.customer_id):
            self.uid = uid

            # bouquet is still visible by user,
            # although one of its tickets is not
            self.assertEqual(
                self.searchUnique(self.bouquet_obj, []),
                self.bouquet.id)
            self.assertNoRecord(
                self.ticket_obj,
                [('id', '=', self.ticket1.id)])

    def test_participant_ids(self):
        # just a very simple case, but better than nothing
        self.assertRecord(
            self.bouquet_obj, self.bouquet.id,
            {'participant_ids': set([self.member_id, self.customer_id])},
            list_to_set=True)

    def test_get_rating(self):
        self.tickets.write({'rating': '2.0'})
        self.assertEquals(self.bouquet.bouquet_rating, 4.0)

    def test_create_member(self):
        """Any member can create a bouquet.
        """
        self.BOUQUET.sudo(self.member_id).create({
            'name': 'member bouquet'})
        self.BOUQUET.sudo(self.member_id).create({
            'name': 'member bouquet',
            'ticket_ids': [6, 0, self.tickets.ids]})
