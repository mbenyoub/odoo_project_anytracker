##############################################################################
#
#    anytracker module for OpenERP, Ticket module
#    Copyright (C) 2012 Anybox (<http://www.anybox.fr>)
#                Colin GOUTTE <cgoute@anybox.fr>
#                Christophe COMBELLES <ccomb@anybox.fr>
#                Simon ANDRE <sandre@anybox.fr>
#                Jean Sebastien SUZANNE <jssuzanne@anybox.fr>
#
#    This file is a part of anytracker
#
#    anytracker is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    anytracker is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    "name": "web_anytracker",
    "category": "Generic Modules/Others",
    "description":
        """
        Hierarchical task manager
        """,
    "version": "0.1",
    "depends": ['anytracker'],
    "js": ["static/*/*.js", "static/*/js/*.js"],
    "css": ["static/*/css/*.css"],
    'active': True,
    'web_preload': True,
}
