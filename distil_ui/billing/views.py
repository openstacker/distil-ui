# Copyright (c) 2014 Catalyst IT Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json

from django.template import defaultfilters
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import tables as horizon_tables
from horizon.utils import csvbase
from openstack_dashboard.contrib.management import api
from openstack_dashboard.contrib.management.billing import base
from openstack_dashboard.contrib.management.billing import tables


class IndexCsvRenderer(csvbase.BaseCsvResponse):
    columns = [_("Resource"), _("Count"), _("Cost")]

    def get_row_data(self):
        for b in self.context['current_month']:
            yield (b.resource,
                   b.count,
                   defaultfilters.floatformat(b.cost, 2))


class IndexView(horizon_tables.DataTableView):
    table_class = tables.BillingTable
    show_terminated = True
    csv_template_name = 'management/billing/billing.csv'
    template_name = 'management/billing/index.html'
    csv_response_class = IndexCsvRenderer

    def __init__(self, *args, **kwargs):
        super(IndexView, self).__init__(*args, **kwargs)

    def get_template_names(self):
        if self.request.GET.get('format', 'html') == 'csv':
            return (self.csv_template_name or
                    ".".join((self.template_name.rsplit('.', 1)[0], 'csv')))
        return self.template_name

    def get_content_type(self):
        if self.request.GET.get('format', 'html') == 'csv':
            return "text/csv"
        return "text/html"

    def get_data(self):
        import pdb
        pdb.set_trace()
        try:
            project_id = self.kwargs.get('project_id',
                                         self.request.user.tenant_id)
            self.billing = base.BaseBilling(self.request, project_id)
            self.start, self.end = self.billing.get_date_range()
            distil_client = api.distilclient(self.request)
            self.history = (api.get_cost(self.request, distil_client))

            self.kwargs['billing'] = self.billing
            self.kwargs['current_month'] = self.history[-1][1]
            self.kwargs['history'] = self.history
            return self.history[-1][1]
        except Exception:
            exceptions.handle(self.request, _('Unable to get usage cost.'))
            return []

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['table'].kwargs['billing'] = self.billing
        context['form'] = self.billing.form
        context['billing'] = self.billing
        context['current_month'] = self.history[-1][1]
        pie_data = [{"value": b.cost, "key": b.resource}
                    for b in self.history[-1][1] if b.cost >= 0]
        line_data = [{"values": [{"y": m[0], "x": i}
                                 for i, m in enumerate(self.history)],
                      "method": "Square Root Choice", "key": "Cost"}]
        chart_data = {'pie': pie_data, 'line': line_data}
        context['chart_data'] = json.dumps(chart_data)
        context['amount_cost'] = self.history[-1][0]
        context['cost_details'] = json.dumps(self.history[-1][2])
        context['x_axis_line_chart'] = self._get_x_axis_for_line_chart()
        return context

    def _get_x_axis_for_line_chart(self):
        today = datetime.date.today()
        ordered_month = ['Jan ' + str(today.year), 'Feb', 'Mar', "Apr", 'May',
                         'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        return ordered_month[today.month:] + ordered_month[:today.month]

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('format', 'html') == 'csv':
            render_class = self.csv_response_class
            fn_template = "usage_cost_{0}_{1}.csv"
            filename = fn_template.format(self.start.strftime('%Y-%m-%d'),
                                          self.end.strftime('%Y-%m-%d'))
            response_kwargs.setdefault("filename", filename)
        else:
            render_class = self.response_class
        resp = render_class(request=self.request,
                            template=self.get_template_names(),
                            context=context,
                            content_type=self.get_content_type(),
                            **response_kwargs)
        return resp
