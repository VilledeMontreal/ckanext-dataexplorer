import logging
import json

from flask import Blueprint, make_response, Response
from ckan import model
# from ckan.common import response
from ckan.plugins import toolkit
from ckan.plugins.toolkit import (abort, ObjectNotFound, ValidationError,
                                  c, _, request, config)
# from ckan.plugins.toolkit import response
from ckanext.dataexplorer.lib import FileWriterService

log = logging.getLogger(__name__)

DUMP_FORMATS = 'csv', 'xlsx', 'json', 'xml'

dataexplorer = Blueprint('dataexplorer', __name__)


def _get_ctx():
    return {
        'model': model, 'session': model.Session,
        'user': c.user,
        'auth_user_obj': c.userobj,
        'for_view': True
    }


def _get_action(action, data_dict):
    return toolkit.get_action(action)(_get_ctx(), data_dict)


def extract():
    writer = FileWriterService()
    columns = []
    
    if request.method == 'POST':
        data_dict = dict(request.form)
        data = json.loads(data_dict['extract_data'])
        data['limit'] = config.get('ckanext.dataexplorer.extract_rows_limit',
                                    30000)
        format = data.pop('format')

        resource_meta = _get_action('resource_show',
                                         {'id': data['resource_id']})

        name = resource_meta.get('name', "extract").replace(' ', '_')

        try:
            resource_data = _get_action('datastore_search', data)

            for key in resource_data['fields']:
                columns.append(key['id'])

            # try:
            #     columns.remove('_id')
            # except ValueError:
            #     pass
            try:
                columns.remove('_full_count')
            except ValueError:
                pass
            try:
                columns.remove('rank')
            except ValueError:
                pass

        except ObjectNotFound:
            abort(404, _('DataStore resource not found'))

        try:
            print('::::::columns', columns)
            print('::::::::records', resource_data.get('records'))
            return writer.write_to_file(columns,
                                 resource_data.get('records'),
                                 format,
                                 name)

        except ValidationError:
            abort(400, _(
                u'Format: must be one of %s') % u', '.join(DUMP_FORMATS))

dataexplorer.add_url_rule('/dataexplorer/extract', view_func=extract, methods=['GET', 'POST'])