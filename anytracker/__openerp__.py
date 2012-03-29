{
    'name' : 'anytracker',
    'version' : '0.1',
    'author' : 'cgoutte',
    'website' : 'http://anybox.fr',
    'category' : 'Generic Modules/Others',
    'depends' : ['base','process'],
    'description' : 'Ticket Module',
    'init_xml' : ['anytracker_view.xml'],
    'demo_xml' : ['anytracker_view.xml',],
    'update_xml' : [
                'anytracker_view.xml',
                'ticket_data.xml',
                'process/process_forfait.xml',
                'process/process_tma.xml'],
    'active': False,
    'installable': True
}

